## Règles générales

- Tous les montants sont en réais brésiliens (BRL).
- La date de référence pour toute analyse dans le temps est orders.order_purchase_timestamp.
- Ne jamais joindre order_items et payments dans la même requête sans agréger l'une des deux avant : chaque article serait multiplié par chaque paiement (explosion de jointure) et les sommes seraient fausses.
- Pour afficher une catégorie de produit, utiliser le nom anglais (category_translation.product_category_name_english) avec un LEFT JOIN.

## Nombre de commandes

Définition : nombre de commandes passées, hors commandes annulées ou indisponibles.
Règles :
- Exclure order_status IN ('canceled', 'unavailable').
- Les commandes en cours (shipped, invoiced, processing, created, approved) sont comptées : elles représentent une demande réelle.
- Exception : pour le panier moyen, on utilise les commandes livrées, par cohérence avec le chiffre d'affaires.

SQL de référence :
```sql
SELECT COUNT(DISTINCT order_id) AS nb_commandes
FROM orders
WHERE order_status NOT IN ('canceled', 'unavailable')
```

## Panier moyen

Définition : chiffre d'affaires moyen par commande livrée, hors frais de port.
Règles :
- Panier moyen = chiffre d'affaires / nombre de commandes livrées.
- Calculer par commande, pas par article : diviser par COUNT(DISTINCT order_id), pas par COUNT(*).
- Uniquement les commandes avec order_status = 'delivered'.

SQL de référence :
```sql
SELECT SUM(i.price) / COUNT(DISTINCT o.order_id) AS panier_moyen
FROM orders o
JOIN order_items i ON o.order_id = i.order_id
WHERE o.order_status = 'delivered'
```

## Taux de réachat (clients fidèles)

Définition : part des clients ayant passé au moins deux commandes.
Règles :
- Un client = un customer_unique_id.
- Un client fidèle = un client avec au moins 2 commandes non annulées.
- Le taux de réachat est très faible sur Olist (environ 3 %) : la plupart des clients n'achètent qu'une fois.

SQL de référence :
```sql
WITH commandes_par_client AS (
    SELECT c.customer_unique_id,
           COUNT(DISTINCT o.order_id) AS nb_commandes
    FROM orders o
    JOIN customers c ON o.customer_id = c.customer_id
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
    GROUP BY c.customer_unique_id
)
SELECT AVG(CASE WHEN nb_commandes >= 2 THEN 1.0 ELSE 0.0 END) AS taux_reachat
FROM commandes_par_client
```

## Retard de livraison

Définition : une commande est en retard si elle a été livrée après la date promise au client, en comparant les dates au jour près.
Règles :
- Ne considérer que les commandes livrées : order_status = 'delivered' ET order_delivered_customer_date non vide.
- En retard si CAST(order_delivered_customer_date AS DATE) > CAST(order_estimated_delivery_date AS DATE).
- Taux de retard = commandes en retard / commandes livrées.

SQL de référence (taux de retard) :
```sql
SELECT AVG(CASE WHEN CAST(order_delivered_customer_date AS DATE)
                   > CAST(order_estimated_delivery_date AS DATE)
                THEN 1.0 ELSE 0.0 END) AS taux_retard
FROM orders
WHERE order_status = 'delivered'
  AND order_delivered_customer_date IS NOT NULL
```

## Délai de livraison

Définition : nombre de jours entre l'achat et la livraison au client.
Règles :
- Ne considérer que les commandes livrées avec une date de livraison renseignée.
- Délai = DATE_DIFF('day', order_purchase_timestamp, order_delivered_customer_date).
- Pour un délai « typique », la médiane est souvent plus représentative que la moyenne (quelques livraisons très longues tirent la moyenne vers le haut).

SQL de référence :
```sql
SELECT AVG(DATE_DIFF('day', order_purchase_timestamp, order_delivered_customer_date)) AS delai_moyen_jours,
       MEDIAN(DATE_DIFF('day', order_purchase_timestamp, order_delivered_customer_date)) AS delai_median_jours
FROM orders
WHERE order_status = 'delivered'
  AND order_delivered_customer_date IS NOT NULL
```

## Satisfaction client et avis négatifs

Définition : la satisfaction se mesure avec reviews.review_score (de 1 à 5).
Règles :
- Note moyenne = AVG(review_score).
- Un avis négatif = une note de 1 ou 2. Un avis positif = une note de 4 ou 5. Une note de 3 est neutre.
- Taux d'avis négatifs = avis négatifs / total des avis.
- Les notes sont très polarisées : environ 57 % de 5/5, mais un pic à 1/5 (environ 11 %).

SQL de référence (taux d'avis négatifs par catégorie) :
```sql
SELECT COALESCE(t.product_category_name_english, p.product_category_name) AS categorie,
       AVG(CASE WHEN r.review_score <= 2 THEN 1.0 ELSE 0.0 END) AS taux_avis_negatifs,
       COUNT(*) AS nb_avis
FROM reviews r
JOIN order_items i ON r.order_id = i.order_id
JOIN products p ON i.product_id = p.product_id
LEFT JOIN category_translation t ON p.product_category_name = t.product_category_name
GROUP BY categorie
ORDER BY taux_avis_negatifs DESC
```

## Régions du Brésil

Les utilisateurs parlent de régions, mais la base ne contient que des codes d'États (customers.customer_state, sellers.seller_state).
Correspondance :
- Sud : PR, SC, RS
- Sud-Est : SP, RJ, MG, ES
- Centre-Ouest : MT, MS, GO, DF
- Nord-Est : MA, PI, CE, RN, PB, PE, AL, SE, BA
- Nord : AM, RR, AP, PA, TO, RO, AC

SQL de référence (filtre « dans le Sud ») :
```sql
WHERE c.customer_state IN ('PR', 'SC', 'RS')
```

## Période des données et expressions de temps

Les données couvrent les commandes de 2016 à 2018. Les premiers et derniers mois contiennent très peu de commandes.
Règles :
- « Récemment », « le dernier mois », « ce mois-ci » = le mois de la dernière date d'achat disponible, calculé avec MAX(order_purchase_timestamp). Ne jamais utiliser la date du jour (CURRENT_DATE) : les données s'arrêtent en 2018.
- « Cette année » = l'année de la dernière date d'achat disponible.
- Le dernier mois disponible peut être incomplet. Quand une réponse porte sur ce mois ou le compare aux précédents, le signaler à l'utilisateur.

SQL de référence (dernier mois disponible) :
```sql
WITH dernier_mois AS (
    SELECT DATE_TRUNC('month', MAX(order_purchase_timestamp)) AS mois FROM orders
)
SELECT COUNT(DISTINCT o.order_id) AS nb_commandes
FROM orders o, dernier_mois d
WHERE DATE_TRUNC('month', o.order_purchase_timestamp) = d.mois
  AND o.order_status NOT IN ('canceled', 'unavailable')
```