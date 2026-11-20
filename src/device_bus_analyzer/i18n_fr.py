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
only_bad | Erreurs CRC uniquement
count | Nombre
distinct | Valeurs distinctes
evidence | Preuve
no_data | Pas encore de données.
gaps | Trous / pertes
sessions | Démarrages
ok | valide
bad | erreur CRC
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
decoder_note | Le décodeur dépend du fabricant et est fixé une fois l'appareil créé.
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
model_hint | Suggestions du catalogue. Vos propres valeurs seront proposées à nouveau la prochaine fois.
brand_other_note | Les autres fabricants nécessitent le choix d'un décodeur.
companion | Assistant
cp_title | Assistant
cp_intro | Placez-vous devant l'appareil et dites à l'appli ce que vous faites. Chaque action est chronométrée sur le serveur et comparée au trafic du bus. Rien n'est envoyé à l'appareil.
cp_tip | Astuce : laissez l'appareil au repos environ deux minutes avant de commencer, pour que l'analyse sache quelles valeurs changent d'elles-mêmes.
cp_guided | Vérifications guidées
cp_guided_hint | Chaque étape est chronométrée de « Go » à « Terminé » : votre temps de réaction n'a donc pas d'importance.
cp_free | Marquer une action
cp_menu_label | Menu / affichage (facultatif)
cp_menu_hint | Où êtes-vous dans le menu ? Cela est enregistré avec chaque action.
cp_go | Go
cp_done | Terminé
cp_abort | Arrêter
cp_step | Étape {} sur {}
cp_round | Tour {}
cp_doing | Faites-le maintenant, puis touchez Terminé.
cp_note_label | Que montre l'affichage / quelle option ?
cp_note_needed | Saisissez-le d'abord.
cp_hint_none | Rien d'inhabituel vu sur le bus pour l'instant.
cp_hint_some | {} changement(s) inhabituel(s) vu(s) sur le bus.
cp_hint_nobase | Trop peu de données au repos pour juger.
cp_finished | Toutes les étapes sont terminées.
cp_results | Voir les résultats
cp_recent | Marqué récemment
cp_custom | Autre action
cp_custom_label | Qu'avez-vous fait ?
cp_add | Marquer
cp_empty | Rien de marqué pour l'instant.
cp_remove | Retirer
cp_error | Cela n'a pas fonctionné. Se reconnecter ?
cp_tap_note | Saisissez le détail, puis touchez Marquer.
cp_duration | {} s
learn | Appris
learn_title | Ce que dit le bus
learn_intro | Pour chaque action, les octets avant et après sont comparés. Un octet compte lorsqu'il change à chaque fois pour la même action et ne change pas tout seul. Les actions opposées (ouvert / fermé) doivent remettre le même octet dans son état initial.
learn_none | Aucune action marquée pour l'instant. Ouvrez l'assistant et marquez ce que vous faites.
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
open_companion | Ouvrir l'assistant
not_accepted | Pas encore assez de preuves
times | fois
of_n | sur
cp_what | Action
state_now | Maintenant
values_title | Valeurs de l'affichage
values_intro | Ces octets suivent les nombres que vous lisez sur l'affichage (temps restant, température). Acceptez-en un pour voir la valeur dans les listes de télégrammes et sur l'appareil.
encoding | Format
unit | Unité
display_value | Valeur affichée
need_readings | Lisez l'affichage au moins quatre fois avec des valeurs différentes (vérification guidée « Lire l'affichage »).
spec_suggestion | Proposition de spécification (YAML)
ha_title | Home Assistant
ha_intro | Tout ce que vous avez appris à l'appli, sous forme de valeurs actuelles pour Home Assistant. Home Assistant les lit sur ce serveur avec le jeton d'API ; l'appareil n'est jamais contacté.
ha_none | Rien d'appris pour l'instant. Acceptez d'abord des résultats ou des valeurs d'affichage sur la page Appris.
ha_now | Maintenant
ha_step1 | Placez le jeton d'API dans secrets.yaml sous dba_bearer (valeur : Bearer suivi du jeton).
ha_step2 | Ajoutez le YAML ci-dessous à configuration.yaml, puis redémarrez ou rechargez Home Assistant.
help_link | Aide
backup_link | Sauvegarde
help_title | Comment enregistrer un bon cycle
help_intro | Quelques minutes de soin devant l'appareil rendent les résultats fiables.
help_step1 | Créez l'appareil (type, fabricant, modèle) et flashez le firmware recommandé. Attendez que la carte de l'appareil affiche des données.
help_step2 | Ouvrez l'assistant et lancez une vérification guidée, par exemple porte ouverte et fermée. Effectuez chaque action sur l'appareil exactement quand l'appli le demande.
help_step3 | Répétez chaque action au moins trois fois, avec quelques secondes de pause entre chaque. Les répétitions transforment une hypothèse en résultat confirmé.
help_step4 | Pour les cycles de programme : démarrez le marqueur, appuyez sur le bouton de l'appareil, touchez Terminé dès qu'il réagit. Un marqueur par appui.
help_step5 | Pour les valeurs de l'affichage : lisez l'affichage et saisissez-le cinq fois pendant qu'il change (temps restant, température).
help_step6 | Ouvrez Appris, vérifiez les propositions et acceptez celles qui correspondent à ce que vous avez vu. Les propositions erronées peuvent être supprimées.
help_step7 | Exportez les résultats : ils ne contiennent ni télégrammes, ni heures, ni adresses, ni clés et peuvent être envoyés au projet.
help_why_title | Pourquoi tant de soin ?
help_why | L'appli ne fait qu'écouter. Elle compare les octets avant et après votre action avec le bruit normal du bus ; un bon chronométrage et des répétitions rendent cette comparaison fiable.
help_share_title | Partage
help_share | Utilisez l'export de la page Appris, ou la proposition de spécification, et ajoutez le fichier sous contributions/ dans le dépôt du projet.
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
onb_marker | Enregistrer une action dans l'assistant
onb_learned | Accepter un résultat sur la page Appris
"""
