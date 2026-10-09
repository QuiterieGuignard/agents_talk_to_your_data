# Dictionnaire de données — Olist

Base e-commerce de la marketplace brésilienne Olist (commandes de 2016 à 2018).
Tous les montants sont en réais brésiliens (BRL).

## Table orders

Table centrale : une ligne = une commande. Clé primaire : order_id.

Colonnes :
- order_id : identifiant unique de la commande.
- customer_id : identifiant client propre à CETTE commande (un nouveau customer_id est créé à chaque commande). Sert uniquement à joindre la table customers. Ne jamais l'utiliser pour compter des clients.
- order_status : statut de la commande. Valeurs : delivered, shipped, canceled, unavailable, invoiced, processing, created, approved.
- order_purchase_timestamp : date et heure de l'achat. C'est LA date de référence pour toute analyse dans le temps.
- order_approved_at : date de validation du paiement.
- order_delivered_carrier_date : date de remise au transporteur.
- order_delivered_customer_date : date de livraison réelle au client. Vide si la commande n'est pas livrée.
- order_estimated_delivery_date : date de livraison promise au client au moment de l'achat.

Jointures :
- orders.order_id = order_items.order_id (une commande a un ou plusieurs articles)
- orders.order_id = payments.order_id
- orders.order_id = reviews.order_id
- orders.customer_id = customers.customer_id

## Table order_items

Une ligne = un article dans une commande. Une commande de 3 articles a 3 lignes.

Colonnes :
- order_id : commande à laquelle appartient l'article.
- order_item_id : numéro de l'article dans la commande (1, 2, 3...). Ce n'est PAS une quantité.
- product_id : produit vendu.
- seller_id : vendeur de cet article. Une même commande peut contenir des articles de vendeurs différents.
- shipping_limit_date : date limite d'expédition pour le vendeur.
- price : prix de l'article en BRL, hors frais de port.
- freight_value : frais de port de l'article en BRL.

Pièges :
- Il n'existe pas de colonne quantité. Un produit acheté deux fois apparaît sur deux lignes. Nombre d'articles vendus = COUNT(*) sur order_items.

Jointures :
- order_items.order_id = orders.order_id
- order_items.product_id = products.product_id
- order_items.seller_id = sellers.seller_id
## Table customers

Une ligne = un client POUR UNE COMMANDE donnée (pas une personne). Clé : customer_id.

Colonnes :
- customer_id : identifiant client propre à une commande. Il y a exactement un customer_id par commande. Sert uniquement à joindre la table orders.
- customer_unique_id : identifiant de la personne réelle. Une même personne garde le même customer_unique_id sur toutes ses commandes. C'est LA colonne à utiliser pour compter des clients ou étudier les réachats.
- customer_zip_code_prefix : 5 premiers chiffres du code postal du client, stocké comme texte (ex. : '01151').
- customer_city : ville du client, en minuscules et sans accents (ex. : sao paulo, rio de janeiro).
- customer_state : État du client, code à deux lettres (ex. : SP = São Paulo, RJ = Rio de Janeiro, MG = Minas Gerais).

Pièges :
- Nombre de clients = COUNT(DISTINCT customer_unique_id), jamais COUNT(DISTINCT customer_id).
- Pour une analyse géographique des ventes, utiliser customer_state (où le client est livré), pas seller_state.

Jointures :
- customers.customer_id = orders.customer_id

## Table products

Une ligne = un produit du catalogue. Clé : product_id.

Colonnes :
- product_id : identifiant unique du produit.
- product_category_name : catégorie du produit EN PORTUGAIS (ex. : beleza_saude, cama_mesa_banho). Peut être vide.
- product_name_lenght : nombre de caractères du nom du produit. Attention, le nom de colonne contient une faute d'orthographe ("lenght") et doit être écrit exactement ainsi.
- product_description_lenght : nombre de caractères de la description. Même faute d'orthographe ("lenght").
- product_photos_qty : nombre de photos sur la fiche produit.
- product_weight_g : poids du produit en grammes.
- product_length_cm, product_height_cm, product_width_cm : dimensions du produit en centimètres (ici, "length" est bien orthographié).

Pièges :
- Le nom réel des produits n'existe pas dans la base : on ne connaît que leur catégorie.
- Les catégories sont en portugais. Pour afficher un nom lisible, joindre category_translation pour obtenir le nom en anglais.
- Certains produits n'ont pas de catégorie (product_category_name vide). Un JOIN sur category_translation les exclut : utiliser LEFT JOIN pour les totaux.
- 610 produits n'ont pas de catégorie.

Jointures :
- products.product_id = order_items.product_id
- products.product_category_name = category_translation.product_category_name

## Table sellers

Une ligne = un vendeur de la marketplace. Clé : seller_id.

Colonnes :
- seller_id : identifiant unique du vendeur.
- seller_zip_code_prefix : 5 premiers chiffres du code postal du vendeur (zéro initial perdu, comme pour les clients).
- seller_city : ville du vendeur, en minuscules et sans accents.
- seller_state : État du vendeur, code à deux lettres (ex. : SP, RJ).

Pièges :
- Un vendeur n'est pas rattaché à une commande mais à un article : passer par order_items pour relier vendeurs et commandes.
- Une même commande peut contenir des articles de plusieurs vendeurs.

Jointures :
- sellers.seller_id = order_items.seller_id

## Table payments

Une ligne = un moyen de paiement utilisé pour une commande. Une commande peut avoir plusieurs lignes (ex. : carte bancaire + bon d'achat).

Colonnes :
- order_id : commande payée.
- payment_sequential : numéro du paiement dans la commande (1, 2, 3...), quand plusieurs moyens de paiement sont combinés.
- payment_type : moyen de paiement. Valeurs : credit_card (carte de crédit), boleto (bordereau bancaire brésilien, payé en espèces ou par virement), voucher (bon d'achat), debit_card (carte de débit), not_defined.
- payment_installments : nombre de mensualités choisies (paiement en plusieurs fois, très courant au Brésil). 1 = paiement comptant.
- payment_value : montant de ce paiement en BRL. Il inclut les frais de port.

Pièges :
- Montant total payé pour une commande = SUM(payment_value) groupé par order_id.
- Ne jamais joindre payments et order_items dans la même requête sans avoir agrégé l'une des deux avant : chaque article serait multiplié par chaque paiement, et les sommes seraient gonflées.
- Ne pas utiliser payment_value pour calculer le chiffre d'affaires (voir glossaire).
2 961 commandes ont plusieurs lignes de paiement. La carte de crédit domine largement (environ 74 % des paiements), suivie du boleto (environ 19 %).

Jointures :
- payments.order_id = orders.order_id

## Table reviews

Une ligne = un avis client laissé après une commande (enquête de satisfaction envoyée par e-mail).

Colonnes :
- review_id : identifiant de l'avis.
- order_id : commande évaluée.
- review_score : note de 1 (très insatisfait) à 5 (très satisfait).
- review_comment_title : titre du commentaire, en portugais. Souvent vide.
- review_comment_message : texte du commentaire, en portugais. S               ouvent vide. Les noms d'entreprises y ont été remplacés par des noms de maisons de Game of Thrones (anonymisation).
- review_creation_date : date d'envoi de l'enquête au client.
- review_answer_timestamp : date de réponse du client.

Pièges :
- Toutes les commandes n'ont pas d'avis, et quelques commandes en ont plusieurs. Pour une note par commande, faire la moyenne par order_id.
- Pour analyser le texte des avis, garder en tête qu'il est en portugais.
- 547 commandes ont plusieurs avis. Les notes sont très majoritairement positives : environ 57 % de 5/5, contre environ 11 % de 1/5.

Jointures :
- reviews.order_id = orders.order_id

## Table category_translation

Table de traduction des catégories de produits du portugais vers l'anglais. Une ligne = une catégorie.

Colonnes :
- product_category_name : nom de la catégorie en portugais (ex. : beleza_saude).
- product_category_name_english : nom de la catégorie en anglais (ex. : health_beauty).

Pièges :
- Quelques catégories présentes dans products n'ont pas de traduction ici. Un JOIN les exclut : utiliser LEFT JOIN et COALESCE(product_category_name_english, product_category_name) pour garder un nom dans tous les cas.
- Les catégories sans traduction sont pc_gamer et portateis_cozinha_e_preparadores_de_alimentos.

Jointures :
- category_translation.product_category_name = products.product_category_name