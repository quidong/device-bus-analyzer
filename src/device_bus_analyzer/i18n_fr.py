"""French UI strings (key | text); the key set must equal the English one (checked by a test)."""
RAW = """
title | Device Bus Analyzer
login | Se connecter
email | Adresse e-mail
password | Mot de passe
logout | Se déconnecter
bad_login | E-mail ou mot de passe incorrect.
locked | Trop de tentatives, réessayez dans quelques minutes.
sources | Sources
frames | Trames
timeline | Chronologie
commands | Commandes
bursts | Rafales brutes
findings | Résultats
quality | Qualité
name | Nom
protocol | Protocole
first | Premier
last | Dernier
time | Heure
dest | Dest.
cmd | Cmd
data | Données
ack | ACK
crc | CRC
decoded | Décodé
status | Statut
filter | Filtrer
since | De
until | À
limit | Limite
with_damaged | inclure les télégrammes endommagés
only_bad | Erreurs CRC uniquement
count | Nombre
distinct | Valeurs distinctes
evidence | Preuve
no_data | Pas encore de données.
gaps | Trous / pertes
sessions | Démarrages
ok | valide
bad | points endommagés (CRC)
not_repeated | dont non répétés intacts
raw_data | avec données brutes (RAW1)
hidden_damaged | Masquées : adresses vues uniquement dans des télégrammes endommagés
show_damaged | afficher
hide_damaged | masquer à nouveau
legacy_data | ancien enregistrement sans données brutes
values | Valeurs
confirmed | confirmé
assumed | supposé
unknown | inconnu
next | Suivant
prev | Précédent
burst_hex | Hex brut
runs | Cycles
run | Cycle
start | Début
end | Fin
duration | Durée
program | Programme
remaining | Restant
running | en cours
runs_note | Un cycle est déduit : il commence à la commande de départ et se termine au dernier télégramme avant un silence. Les deux sont marqués comme supposés.
sender | Émetteur
receiver | Récepteur
nodes | Nœuds
sender_note | La trame ne contient que la destination ; l'émetteur en est déduit et n'est au mieux que supposé.
devices | Appareils
address | Adresse
device | Appareil
devices_note | Les adresses source et destination sont lues dans la trame et sont toujours exactes ; la nature d'un appareil est déduite de son trafic et porte un statut.
timezone_note | Heures en
all | tous
devices_title | Appareils
new_device | Nouvel appareil
edit | Modifier
save | Enregistrer
cancel | Annuler
device_type | Type
manufacturer | Fabricant
model | Modèle
host | Hôte / IP
port | Port
api_key | Clé de chiffrement de l'API
key_set | définie
key_missing | non définie
key_keep | Laissez vide pour conserver la clé enregistrée.
key_clear | Supprimer la clé enregistrée
enabled | Collecter
disabled | en pause
enabled_on | collecte en cours
unclassified | non classé
import_only | import uniquement
connection | Connexion
dev_note | Les appareils sont enregistrés dans le volume de la base de données. Le nom et le décodeur ne peuvent plus être modifiés une fois l'appareil créé.
pick_hint | Choisissez une suggestion ou saisissez votre propre valeur.
protocol_fixed | Le protocole est fixé une fois l'appareil créé.
bad_name | Nom : lettres, chiffres, - et _ uniquement (40 max.).
bad_protocol | Protocole inconnu.
bad_host | Hôte manquant ou invalide.
bad_port | Le port doit être compris entre 1 et 65535.
bad_key | La clé doit être la clé base64 de l'API ESPHome (32 octets).
exists | Un appareil portant ce nom existe déjà.
bad_input | Saisie invalide, ou le nom est déjà utilisé avec un autre protocole.
confirm_mismatch | Le nom ne correspond pas. Rien n'a été supprimé.
delete | Supprimer
delete_title | Supprimer l'appareil
delete_confirm_label | Saisissez le nom pour confirmer
delete_forever | Supprimer définitivement
delete_warn | Ceci supprime définitivement l'appareil et tout ce qui a été enregistré. Impossible d'annuler.
delete_removes | Sera supprimé :
n_bursts | rafales brutes
n_frames | trames
n_heartbeats | signaux de vie
n_sessions | démarrages de la carte
n_gaps | entrées de trous
delete_keep | Les autres appareils ne sont pas touchés.
firmware | Firmware
fw_title | Firmware ESPHome
copy | Copier
copied | Copié
download | Télécharger
back | Retour
close | Fermer
fw_intro | Fichiers ESPHome recommandés pour cette famille d'appareils. Flashez une carte avec eux, puis saisissez son hôte et sa clé d'API sous Appareils.
fw_step1 | Dans ESPHome Device Builder, créez un appareil et collez le YAML (placez le deuxième fichier à côté, s'il y en a un).
fw_step2 | Gardez clés et mots de passe dans secrets.yaml ; utilisez la clé de chiffrement d'API générée pour cet appareil.
fw_step3 | Flashez la carte, puis ajoutez l'appareil ici (Appareils > Nouvel appareil).
device_saved | Appareil enregistré. Voici le firmware qui lui correspond :
to_devices | Retour aux appareils
other | Autre …
other_maker | Nom du fabricant
other_type | Type
decoder | Décodeur
decoder_note | Le décodeur suit le système de bus et est figé une fois l'appareil créé.
key_never | Enregistrée uniquement, jamais réaffichée.
needs_class | Type et modèle pas encore attribués.
assign | Attribuer
st_live | collecte en cours
st_waiting | en attente de l'appareil
st_paused | en pause
st_import | import uniquement
last_seen | Dernière activité
never | jamais
pause | Pause
resume | Reprendre
wz_next | Continuer
step_of | Étape
which_type | Quel type d'appareil ?
which_maker | Quel fabricant ?
which_model | Quel modèle ?
which_conn | Comment est-il connecté ?
firmware_link | Afficher le firmware
ago | il y a {}
s | s
min | min
h | h
d | j
menu | Navigation
more | Plus
choose | Veuillez choisir.
model_hint | Modèles connus de ce fabricant. Absent de la liste ? Saisissez-le : il est conservé et proposé à nouveau la prochaine fois, même si l'appareil est supprimé.
cp_duration | {} s
learn | Appris
learn_title | Ce que dit le bus
learn_intro | Pour chaque action, les octets avant et après sont comparés. Un octet compte lorsqu'il change à chaque fois pour la même action et ne change pas tout seul. Les actions opposées (ouvert / fermé) doivent remettre le même octet dans son état initial.
learn_none | Aucune action enregistrée pour cet appareil.
learn_few_base | L'enregistrement contient trop peu de temps au repos pour distinguer le bruit de l'effet. Laissez l'appareil au repos quelques minutes, puis recommencez.
learn_stats | {} actions, {} télégrammes, {} fenêtres au repos
hits | Succès
change | Changement
noise | Bruit
byte | Octet
accept | Accepter
meaning | Signification
learned_title | Résultats acceptés
learned_none | Rien d'accepté pour l'instant.
export | Exporter les résultats
export_note | L'export ne contient que ce que vous avez accepté : adresses, positions d'octets, valeurs et modèle de l'appareil. Pas de télégrammes, d'heures, de noms d'hôte ni de clés.
no_candidates | Aucun octet n'a changé de façon fiable pour cette action.
events_title | Télégrammes vus uniquement avec cette action
actions | Actions
not_accepted | Pas encore assez de preuves
times | fois
of_n | sur
state_now | Maintenant
values_title | Valeurs de l'affichage
values_intro | Ces octets suivent les nombres que vous lisez sur l'affichage (temps restant, température). Acceptez-en un pour voir la valeur dans les listes de télégrammes et sur l'appareil.
encoding | Format
unit | Unité
display_value | Valeur affichée
spec_suggestion | Proposition de spécification (YAML)
ha_title | Home Assistant
ha_intro | Tout ce que vous avez appris à l'appli, sous forme de valeurs actuelles pour Home Assistant. Home Assistant les lit sur ce serveur avec le jeton d'API ; l'appareil n'est jamais contacté.
ha_none | Rien d'appris pour l'instant. Acceptez d'abord des résultats ou des valeurs d'affichage sur la page Appris.
ha_now | Maintenant
ha_step1 | Placez le jeton d'API dans secrets.yaml sous dba_bearer (valeur : Bearer suivi du jeton).
ha_step2 | Ajoutez le YAML ci-dessous à configuration.yaml, puis redémarrez ou rechargez Home Assistant.
help_link | Aide
backup_link | Sauvegarde
help_title | De l'enregistrement au résultat
help_intro | L'application ne fait qu'enregistrer et décoder ce qu'elle connaît déjà. L'analyse est faite par Claude via la connexion IA (MCP).
help_step1 | Créez l'appareil. Le type, le fabricant et le modèle sont obligatoires, car ils décident de ce qui est général et de ce qui est propre au modèle. Flashez le firmware recommandé et attendez que la carte affiche des données.
help_step2 | Enregistrez des cycles complets : choisissez un programme, lancez-le et laissez-le se terminer. Notez ce que vous faites sur l'appareil et quand (p. ex. « 20:14 porte ouverte »).
help_step3 | Répétez plusieurs fois les actions intéressantes avec quelques secondes de pause. Les répétitions transforment une supposition en résultat confirmé.
help_step4 | Connectez Claude : menu du compte → Connexion IA. Installez l'extension et saisissez l'adresse et le jeton d'API.
help_step5 | Laissez Claude analyser le cycle. Des prompts d'exemple se trouvent sur la page Connexion IA ; ajoutez vos notes avec l'heure.
help_step6 | « Analysé » sur la carte de l'appareil indique combien de types de trame (destination + commande) la spécification ou un résultat accepté explique déjà, quelle que soit leur fréquence d'envoi.
help_step7 | Partagez ce que vous avez trouvé avec le projet (voir ci-dessous), pour que les suivants partent avec plus de connaissances.
help_why_title | Pourquoi tant de soin ?
help_why | L'application ne fait qu'écouter et n'envoie jamais rien à l'appareil. Claude compare les trames à vos notes et à la spécification existante ; des heures exactes et des répétitions rendent la comparaison fiable.
help_share_title | Partager avec le projet
help_share | Il y a deux façons. Soit fournir des cycles complets : Claude exporte un cycle avec des temps relatifs à son début et sans noms d'hôte, adresses ni clés, et vous le joignez à une issue. Soit partager des résultats analysés : Claude rédige un fichier de contribution pour contributions/ (type, fabricant, modèle, positions d'octets avec statut ; ni trames, ni heures, ni adresses, ni clés). La CI vérifie chaque fichier.
backup_title | Sauvegarde
backup_download | Télécharger une sauvegarde
backup_download_intro | Une copie cohérente de tous les appareils, télégrammes, marqueurs et résultats dans un seul fichier.
backup_keys_warning | Le fichier contient les clés ESPHome enregistrées. Gardez-le privé.
backup_download_btn | Télécharger la sauvegarde
backup_restore | Restaurer une sauvegarde
backup_restore_intro | Remplace tout le contenu de cette installation par celui du fichier. Une copie de sécurité n'est conservée que pendant la restauration : téléchargez donc d'abord une sauvegarde.
backup_file | Fichier de sauvegarde
backup_confirm | Saisissez RESTORE pour confirmer
backup_restore_btn | Restaurer
backup_restored | Sauvegarde restaurée.
backup_err_confirm_mismatch | Saisissez RESTORE pour confirmer.
backup_err_not_sqlite | Ce n'est pas un fichier de sauvegarde valide.
backup_err_integrity | Le fichier est endommagé.
backup_err_missing_tables | Le fichier n'est pas une sauvegarde de Device Bus Analyzer.
backup_err_too_big | Le fichier est trop volumineux.
onb_title | Premiers pas
onb_device | Créer un appareil
onb_data | Recevoir les premiers télégrammes
mcp_link | Connexion IA
mcp_title | Connexion IA (MCP)
mcp_intro | Pour que Claude puisse lire et analyser vos enregistrements, il faut l'extension et deux valeurs : l'adresse de cette installation et le jeton d'API. L'extension ne fait que lire et n'envoie jamais rien à un appareil.
mcp_step1 | Téléchargez l'extension et ouvrez-la d'un double clic (Claude Desktop demande de l'installer).
mcp_step2 | Lors de l'installation, saisissez l'adresse et le jeton d'API ci-dessous.
mcp_download | Télécharger l'extension (.mcpb)
mcp_url | Adresse de cette installation
mcp_url_note | L'adresse doit être joignable depuis l'ordinateur où tourne Claude. Elle est reprise du navigateur ; avec localhost, saisissez l'adresse du réseau local.
mcp_token | Jeton d'API
mcp_token_show | Afficher le jeton
mcp_token_warn | Le jeton donne un accès en lecture à tous les enregistrements. Ne le partagez pas.
mcp_token_none | Aucun jeton d'API n'est défini. Définissez DBA_API_TOKEN dans le conteneur et redémarrez-le.
mcp_other | Claude Code
mcp_other_note | Le serveur tourne en local avec Node (stdio). Adaptez le chemin vers le dossier extension/ du dépôt :
mcp_local_title | Uniquement en local
mcp_local | La connexion est conçue pour un usage local et fonctionne uniquement avec Claude (Claude Desktop et Claude Code). L'analyseur n'est pas exposé sur Internet ; l'extension tourne sur votre ordinateur et lit via le réseau local. Les autres services d'IA comme ChatGPT ne sont pas pris en charge.
copy_cmd | Copier la commande
kn_link | Connaissances des appareils
kn_title | Mettre à jour les connaissances des appareils
kn_intro | Les résultats de protocole, le catalogue d'appareils et le firmware recommandé viennent du projet GitHub et peuvent être mis à jour sans nouvelle image de conteneur. Les données enregistrées ne sont pas touchées ; le décodage utilise aussitôt le nouvel état.
kn_active | Version active
kn_bundled | Fournie dans l'image
kn_src_update | mise à jour téléchargée
kn_src_bundled | fournie
kn_last | Dernière vérification
kn_never | jamais
kn_check | Vérifier maintenant
kn_auto | Vérifier automatiquement chaque jour
kn_save | Enregistrer
kn_reset | Revenir à la version fournie
kn_res_updated | Mis à jour vers
kn_res_current | Déjà à jour.
kn_res_error | Échec
kn_res_needs_app_update | La mise à jour nécessite une version plus récente de l'appli (nouvelle image).
kn_note | Seuls des fichiers de données (YAML) sont téléchargés, vérifiés et activés uniquement si tout est valide. Le conteneur a besoin d'un accès HTTPS sortant vers GitHub.
backup_err_active_content | Le fichier contient des déclencheurs ou des vues et n'est pas restauré pour des raisons de sécurité.
tls_link | HTTPS
tls_title | HTTPS dans le réseau local
tls_intro | L'analyseur utilise HTTPS avec un certificat de sa propre autorité de certification (CA) locale. Installez le certificat de la CA une fois sur vos appareils et l'avertissement du navigateur disparaît.
tls_state | Connexion
tls_not_https | cette page a été chargée sans chiffrement
tls_hosts | Valable pour
tls_expires | Expire
tls_fp | Empreinte de la CA (SHA-256)
tls_download | Télécharger le certificat de la CA
tls_no_ca | Il n'y a pas de CA locale : HTTPS est désactivé ou utilise votre propre certificat.
tls_how | Installer le certificat de la CA
tls_how_ios | téléchargez le fichier, installez le profil dans Réglages, puis activez-le sous Général > Informations > Réglages de confiance des certificats.
tls_how_android | Paramètres > Sécurité > Chiffrement et identifiants > Installer un certificat > Certificat d'autorité.
tls_how_windows | double-cliquez sur le fichier > Installer le certificat > Ordinateur local > Autorités de certification racines de confiance.
tls_how_mac | ouvrez le fichier (Trousseau d'accès), double-cliquez sur le certificat > Confiance > Toujours approuver.
tls_how_firefox | Paramètres > Vie privée et sécurité > Afficher les certificats > Autorités > Importer (ou utiliser les certificats du système).
tls_names | Noms et adresses dans le certificat
tls_names_note | Pour que l'adresse utilisée pour ouvrir l'analyseur corresponde, indiquez-la dans DBA_TLS_HOSTS (séparée par des virgules, noms et adresses IP) et redémarrez le conteneur ; le certificat est réémis et la CA reste la même.
mcp_ca | Si l'analyseur utilise HTTPS avec sa propre CA, choisissez aussi le certificat de la CA comme fichier CA pendant l'installation (téléchargement sur la page HTTPS).
kn_sig | Signature
kn_sig_on | Les mises à jour doivent être signées avec la clé du projet (Ed25519)
kn_sig_off | non imposée : seulement des sommes de contrôle via HTTPS
account | Compte et réglages
language | Langue
live_note | Se met à jour automatiquement
cfg_link | Réglages
cfg_title | Réglages
cfg_intro | Modifiez ici les valeurs de l'installation sans toucher au stack. Ce qui est enregistré ici prime sur les variables du stack.
cfg_general | Général
cfg_tz | Fuseau horaire d'affichage
cfg_tz_hint | p. ex. Europe/Paris
cfg_hours | Connexion valide (heures)
cfg_kn_url | Adresse des mises à jour
cfg_kn_hint | Vide pour le dépôt du projet.
cfg_https | HTTPS
cfg_tls_on | Activer HTTPS (redémarrage requis)
cfg_tls_hosts | Noms/adresses supplémentaires dans le certificat
cfg_save | Enregistrer
cfg_token | Jeton d'API
cfg_token_note | Le jeton de la connexion IA. Une fois renouvelé, l'ancien cesse de fonctionner ; un jeton défini dans le stack redevient actif après un redémarrage, retirez-le là.
cfg_token_new | Générer un nouveau jeton
cfg_password | Changer le mot de passe
cfg_pw_current | Mot de passe actuel
cfg_pw_new | Nouveau mot de passe (10 caractères minimum)
cfg_pw_again | Répétez le nouveau mot de passe
cfg_saved | Enregistré.
cfg_restart | Enregistré. Le réglage HTTPS s'applique après le redémarrage du conteneur.
cfg_token_done | Nouveau jeton créé : il figure sur la page connexion IA.
cfg_pw_done | Mot de passe modifié.
cfg_err_tz | Fuseau horaire inconnu.
cfg_err_hours | Validité : 1 à 2160 heures.
cfg_err_url | L'adresse doit commencer par http:// ou https://.
cfg_err_hosts | Nom ou adresse invalide pour le certificat.
cfg_err_pw_current | Le mot de passe actuel est incorrect.
cfg_err_pw_new | Nouveau mot de passe trop court ou la répétition ne correspond pas.
nav_data | Enregistrements
menu_main | Menu principal
menu_account | Compte
menu_connect | Connexions
menu_system | Système
learn_silent | Sans réaction de l'appareil (non comptées – était-il allumé ?) : {}
need_class | Indiquez le type, le fabricant et le modèle : ils décident de ce qui est général et de ce qui est propre au modèle.
analysed | Analysé
analysed_confirmed | {} % confirmé
analysed_of | {} types de trame sur {} (destination + commande) sont expliqués par la spécification ou un résultat accepté ({} confirmés).
open_device | Ouvrir l'appareil
onb_run | Enregistrer un cycle complet (lancer un programme et le laisser se terminer)
onb_mcp | Connecter Claude (connexion IA) et lui faire analyser le cycle
mcp_prompts_title | Prompts pour l'analyse
mcp_prompts_intro | Copiez un prompt dans Claude et remplacez les parties entre chevrons. Plus vos heures sont exactes, plus la réponse est fiable.
mcp_prompt_device | Appareil dans les exemples
mcp_device_ph | <appareil>
mcp_p1_title | Vue d'ensemble
mcp_p1 | Utilise le Device Bus Analyzer pour me donner une vue d'ensemble de l'appareil « {} » : quels cycles existent, quelles commandes apparaissent et lesquelles sont encore inconnues selon la spécification ?
mcp_p2_title | Analyser un cycle avec mes actions
mcp_p2 | Analyse le dernier cycle complet de « {} ». Pendant celui-ci j'ai fait ceci (heure – action, une par ligne) : <...>. Quels octets changent en accord avec mes actions, et avec quelle certitude (répétitions, bruit du bus) ?
mcp_p3_title | Trouver les valeurs affichées
mcp_p3 | Cherche dans les cycles de « {} » des valeurs qui correspondent au temps restant ou à la température affichés. J'ai relevé (heure – valeur) : <...>. Indique la commande, la position d'octet, l'encodage et le facteur.
mcp_p4_title | Interpréter les commandes inconnues
mcp_p4 | Quelles commandes de « {} » sont inconnues mais fréquentes ? Propose une signification pour les trois plus fréquentes et justifie-la par leurs valeurs au fil des cycles.
mcp_p5_title | Partager les résultats (fichier de contribution)
mcp_p5 | Résume les résultats fiables sur « {} » dans un fichier de contribution au format du dossier contributions/ du projet (type, fabricant, modèle, résultats avec position d'octet et statut). Ni trames, ni horodatages, ni adresses, ni clés.
mcp_p6_title | Partager un cycle complet
mcp_p6 | Exporte le cycle <n°> de « {} » en CSV : temps en secondes depuis le début du cycle, destination, commande et données (hex), plus le programme et le type, le fabricant et le modèle. Ni noms d'hôte, ni adresses IP, ni clés.
bus_system | Système de bus
bus_note | Présélectionné selon le fabricant. Changez-le si votre appareil utilise un autre bus ; il est figé une fois l'appareil créé.
login_expired | La page de connexion est restée ouverte trop longtemps. Veuillez saisir à nouveau votre mot de passe.
analysed_types | {} types de trame sur {}
analysed_assumed | {} % supposé
run_waited | + {} min de départ différé
"""
