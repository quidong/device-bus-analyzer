"""Italian UI strings (key | text); the key set must equal the English one (checked by a test)."""
RAW = """
title | Device Bus Analyzer
login | Accedi
email | E-mail
password | Password
logout | Esci
bad_login | E-mail o password errate.
locked | Troppi tentativi, riprova tra qualche minuto.
sources | Sorgenti
frames | Frame
timeline | Cronologia
commands | Comandi
bursts | Burst grezzi
findings | Risultati
quality | Qualità
name | Nome
protocol | Protocollo
first | Primo
last | Ultimo
time | Ora
dest | Dest.
cmd | Cmd
data | Dati
ack | ACK
crc | CRC
decoded | Decodificato
status | Stato
filter | Filtra
since | Da
until | A
limit | Limite
with_damaged | includi telegrammi danneggiati
only_bad | Solo errori CRC
count | Numero
distinct | Valori distinti
evidence | Evidenza
no_data | Ancora nessun dato.
gaps | Buchi / perdite
sessions | Avvii
ok | valido
bad | punti danneggiati (CRC)
not_repeated | di cui non ripetuti integri
raw_data | con dati grezzi (RAW1)
hidden_damaged | Nascoste: indirizzi visti solo in telegrammi danneggiati
show_damaged | mostra
hide_damaged | nascondi di nuovo
legacy_data | registrazione precedente senza dati grezzi
values | Valori
confirmed | confermato
assumed | presunto
unknown | sconosciuto
next | Avanti
prev | Indietro
burst_hex | Hex grezzo
runs | Cicli
run | Ciclo
start | Inizio
end | Fine
duration | Durata
program | Programma
remaining | Rimanente
running | in corso
runs_note | Un ciclo è dedotto: inizia con il comando di avvio e termina con l'ultimo telegramma prima di una pausa. Entrambi sono contrassegnati come presunti.
sender | Mittente
receiver | Destinatario
nodes | Nodi
sender_note | Il frame contiene solo la destinazione; il mittente ne viene dedotto e al massimo è presunto.
devices | Dispositivi
address | Indirizzo
device | Dispositivo
devices_note | Gli indirizzi di origine e destinazione sono letti dal frame e sono sempre veri; cosa sia un dispositivo si deduce dal suo traffico e ha uno stato.
timezone_note | Orari in
all | tutti
devices_title | Dispositivi
new_device | Nuovo dispositivo
edit | Modifica
save | Salva
cancel | Annulla
device_type | Tipo
manufacturer | Produttore
model | Modello
host | Host / IP
port | Porta
api_key | Chiave di cifratura dell'API
key_set | impostata
key_missing | non impostata
key_keep | Lascia vuoto per mantenere la chiave salvata.
key_clear | Rimuovi la chiave salvata
enabled | Raccogli
disabled | in pausa
enabled_on | raccolta in corso
unclassified | non classificato
import_only | solo importazione
connection | Connessione
dev_note | I dispositivi sono salvati nel volume del database. Nome e decodificatore non si possono più cambiare dopo la creazione del dispositivo.
pick_hint | Scegli un suggerimento o scrivi un tuo valore.
protocol_fixed | Il protocollo è fisso dopo la creazione del dispositivo.
bad_name | Nome: solo lettere, cifre, - e _ (max. 40).
bad_protocol | Protocollo sconosciuto.
bad_host | Host mancante o non valido.
bad_port | La porta deve essere tra 1 e 65535.
bad_key | La chiave deve essere la chiave base64 dell'API ESPHome (32 byte).
exists | Esiste già un dispositivo con questo nome.
bad_input | Input non valido, oppure il nome è già usato con un altro protocollo.
confirm_mismatch | Il nome non corrisponde. Non è stato eliminato nulla.
delete | Elimina
delete_title | Elimina dispositivo
delete_confirm_label | Scrivi il nome per confermare
delete_forever | Elimina definitivamente
delete_warn | Questo rimuove in modo permanente il dispositivo e tutto ciò che è stato registrato. Non si può annullare.
delete_removes | Verrà rimosso:
n_bursts | burst grezzi
n_frames | frame
n_heartbeats | heartbeat
n_sessions | avvii della scheda
n_gaps | voci di buchi
delete_keep | Gli altri dispositivi non vengono toccati.
firmware | Firmware
fw_title | Firmware ESPHome
copy | Copia
copied | Copiato
download | Scarica
back | Indietro
close | Chiudi
fw_intro | File ESPHome consigliati per questa famiglia di dispositivi. Flasha una scheda con essi, poi inserisci host e chiave API in Dispositivi.
fw_step1 | In ESPHome Device Builder crea un dispositivo e incolla lo YAML (metti accanto il secondo file, se c'è).
fw_step2 | Tieni chiavi e password in secrets.yaml; usa la chiave di cifratura API generata per questo dispositivo.
fw_step3 | Flasha la scheda, poi aggiungi qui il dispositivo (Dispositivi > Nuovo dispositivo).
device_saved | Dispositivo salvato. Questo è il firmware adatto:
to_devices | Torna ai dispositivi
other | Altro …
other_maker | Nome del produttore
other_type | Tipo
decoder | Decodificatore
decoder_note | Il decodificatore segue il sistema bus ed è fisso una volta creato l'apparecchio.
key_never | Solo salvata, mai più mostrata.
needs_class | Tipo e modello non ancora assegnati.
assign | Assegna
st_live | raccolta in corso
st_waiting | in attesa del dispositivo
st_paused | in pausa
st_import | solo importazione
last_seen | Ultima attività
never | mai
pause | Pausa
resume | Riprendi
wz_next | Continua
step_of | Passo
which_type | Che tipo di dispositivo?
which_maker | Quale produttore?
which_model | Quale modello?
which_conn | Come è collegato?
firmware_link | Mostra firmware
ago | {} fa
s | s
min | min
h | h
d | g
menu | Navigazione
more | Altro
choose | Scegli un'opzione.
model_hint | Modelli noti di questo produttore. Non c'è? Scrivilo: viene salvato e riproposto la prossima volta, anche se l'apparecchio viene eliminato.
cp_duration | {} s
learn | Appreso
learn_title | Cosa dice il bus
learn_intro | Per ogni azione si confrontano i byte prima e dopo. Un byte conta quando cambia ogni volta con la stessa azione e non cambia da solo. Le azioni opposte (aperto / chiuso) devono riportare lo stesso byte al valore di partenza.
learn_none | Nessuna azione registrata per questo apparecchio.
learn_few_base | Nella registrazione c'è troppo poco tempo a riposo per distinguere rumore ed effetto. Lascia l'apparecchio a riposo un paio di minuti, poi ripeti.
learn_stats | {} azioni, {} telegrammi, {} finestre a riposo
hits | Riscontri
change | Cambiamento
noise | Rumore
byte | Byte
accept | Accetta
meaning | Significato
learned_title | Risultati accettati
learned_none | Ancora nulla di accettato.
export | Esporta i risultati
export_note | L'esportazione contiene solo ciò che hai accettato: indirizzi, posizioni dei byte, valori e modello dell'apparecchio. Nessun telegramma, orario, nome host o chiave.
no_candidates | Nessun byte è cambiato in modo affidabile per questa azione.
events_title | Telegrammi visti solo con questa azione
actions | Azioni
not_accepted | Prove ancora insufficienti
times | volte
of_n | su
state_now | Ora
values_title | Valori dal display
values_intro | Questi byte seguono i numeri che leggi sul display (tempo rimanente, temperatura). Accettane uno per vedere il valore negli elenchi dei telegrammi e sul dispositivo.
encoding | Formato
unit | Unità
display_value | Valore del display
spec_suggestion | Proposta di specifica (YAML)
ha_title | Home Assistant
ha_intro | Tutto ciò che hai insegnato all'app, come valori attuali per Home Assistant. Home Assistant li legge da questo server con il token API; l'apparecchio non viene mai contattato.
ha_none | Ancora nulla di insegnato. Accetta prima risultati o valori del display nella pagina Appreso.
ha_now | Ora
ha_step1 | Inserisci il token API in secrets.yaml come dba_bearer (valore: Bearer e il token).
ha_step2 | Aggiungi lo YAML qui sotto a configuration.yaml e riavvia o ricarica Home Assistant.
help_link | Aiuto
backup_link | Backup
help_title | Dalla registrazione al risultato
help_intro | L'app registra e decodifica solo ciò che conosce già. L'analisi la fa Claude tramite la connessione IA (MCP).
help_step1 | Crea l'apparecchio. Tipo, produttore e modello sono obbligatori, perché decidono cosa è generale e cosa è specifico del modello. Installa il firmware consigliato e attendi che la scheda mostri dati.
help_step2 | Registra cicli completi: scegli un programma, avvialo e lascialo finire. Annota cosa fai all'apparecchio e quando (ad es. «20:14 porta aperta»).
help_step3 | Ripeti più volte le azioni interessanti con qualche secondo di pausa. Le ripetizioni trasformano un'ipotesi in un risultato confermato.
help_step4 | Collega Claude: menu account → Connessione IA. Installa l'estensione e inserisci l'indirizzo e il token API.
help_step5 | Lascia che Claude analizzi il ciclo. Prompt di esempio sono nella pagina Connessione IA; aggiungi le tue note con l'orario.
help_step6 | «Analizzato» sulla scheda dell'apparecchio mostra quanti tipi di frame (destinazione + comando) sono già spiegati dalla specifica o da un risultato accettato, indipendentemente da quanto spesso vengono inviati.
help_step7 | Condividi ciò che hai scoperto con il progetto (vedi sotto), così chi viene dopo parte con più conoscenze.
help_why_title | Perché tanta cura?
help_why | L'app ascolta soltanto e non invia mai nulla all'apparecchio. Claude confronta i frame con le tue note e la specifica esistente; orari esatti e ripetizioni rendono affidabile il confronto.
help_share_title | Condividere con il progetto
help_share | Ci sono due strade. O fornire cicli completi: Claude esporta un ciclo con tempi relativi all'inizio e senza nomi host, indirizzi o chiavi, e lo alleghi a una issue. Oppure condividere risultati analizzati: Claude scrive un file di contributo per contributions/ (tipo, produttore, modello, posizioni dei byte con stato; niente frame, orari, indirizzi o chiavi). La CI controlla ogni file.
backup_title | Backup
backup_download | Scarica un backup
backup_download_intro | Una copia coerente di tutti i dispositivi, telegrammi, marcatori e risultati in un unico file.
backup_keys_warning | Il file contiene le chiavi ESPHome salvate. Tienilo privato.
backup_download_btn | Scarica backup
backup_restore | Ripristina un backup
backup_restore_intro | Sostituisce tutto in questa installazione con il contenuto del file. Una copia di sicurezza viene tenuta solo durante il ripristino, quindi scarica prima un backup.
backup_file | File di backup
backup_confirm | Scrivi RESTORE per confermare
backup_restore_btn | Ripristina
backup_restored | Backup ripristinato.
backup_err_confirm_mismatch | Scrivi RESTORE per confermare.
backup_err_not_sqlite | Non è un file di backup valido.
backup_err_integrity | Il file è danneggiato.
backup_err_missing_tables | Il file non è un backup di Device Bus Analyzer.
backup_err_too_big | Il file è troppo grande.
onb_title | Primi passi
onb_device | Crea un dispositivo
onb_data | Ricevi i primi telegrammi
mcp_link | Collegamento IA
mcp_title | Collegamento IA (MCP)
mcp_intro | Perché Claude possa leggere e analizzare le tue registrazioni servono l'estensione e due valori: l'indirizzo di questa installazione e il token API. L'estensione legge soltanto e non invia mai nulla a un dispositivo.
mcp_step1 | Scarica l'estensione e aprila con un doppio clic (Claude Desktop chiede di installarla).
mcp_step2 | Durante l'installazione inserisci l'indirizzo e il token API qui sotto.
mcp_download | Scarica l'estensione (.mcpb)
mcp_url | Indirizzo di questa installazione
mcp_url_note | L'indirizzo deve essere raggiungibile dal computer su cui gira Claude. Viene preso dal browser; se usi localhost, inserisci l'indirizzo della rete locale.
mcp_token | Token API
mcp_token_show | Mostra token
mcp_token_warn | Il token dà accesso in lettura a tutte le registrazioni. Non condividerlo.
mcp_token_none | Nessun token API impostato. Imposta DBA_API_TOKEN nel container e riavvialo.
mcp_other | Claude Code
mcp_other_note | Il server gira in locale con Node (stdio). Adatta il percorso alla cartella extension/ del repository:
mcp_local_title | Solo per uso locale
mcp_local | Il collegamento è pensato per l'uso locale e funziona solo con Claude (Claude Desktop e Claude Code). L'analizzatore non viene messo su internet; l'estensione gira sul tuo computer e legge tramite la rete locale. Altri servizi di IA come ChatGPT non sono supportati.
copy_cmd | Copia comando
kn_link | Conoscenze sui dispositivi
kn_title | Aggiorna le conoscenze sui dispositivi
kn_intro | I risultati sui protocolli, il catalogo dei dispositivi e il firmware consigliato provengono dal progetto GitHub e si aggiornano senza una nuova immagine del container. I dati registrati restano intatti; la decodifica usa subito il nuovo stato.
kn_active | Versione attiva
kn_bundled | Inclusa nell'immagine
kn_src_update | aggiornamento scaricato
kn_src_bundled | inclusa
kn_last | Ultimo controllo
kn_never | mai
kn_check | Controlla ora
kn_auto | Controlla automaticamente ogni giorno
kn_save | Salva
kn_reset | Torna alla versione inclusa
kn_res_updated | Aggiornato a
kn_res_current | Già aggiornato.
kn_res_error | Non riuscito
kn_res_needs_app_update | L'aggiornamento richiede una versione più recente dell'app (nuova immagine).
kn_note | Vengono scaricati solo file di dati (YAML), controllati e attivati solo se tutto è valido. Il container ha bisogno dell'accesso HTTPS in uscita verso GitHub.
backup_err_active_content | Il file contiene trigger o viste e non viene ripristinato per motivi di sicurezza.
tls_link | HTTPS
tls_title | HTTPS nella rete locale
tls_intro | L'analizzatore usa HTTPS con un certificato di una propria autorità di certificazione (CA) locale. Installa il certificato della CA una volta sui tuoi dispositivi e l'avviso del browser scompare.
tls_state | Connessione
tls_not_https | questa pagina è stata caricata senza cifratura
tls_hosts | Valido per
tls_expires | Scade
tls_fp | Impronta della CA (SHA-256)
tls_download | Scarica il certificato della CA
tls_no_ca | Non c'è una CA locale: HTTPS è disattivato o usa il tuo certificato.
tls_how | Installare il certificato della CA
tls_how_ios | scarica il file, installa il profilo in Impostazioni e attivalo in Generali > Info > Impostazioni di attendibilità dei certificati.
tls_how_android | Impostazioni > Sicurezza > Crittografia e credenziali > Installa un certificato > Certificato CA.
tls_how_windows | doppio clic sul file > Installa certificato > Computer locale > Autorità di certificazione radice attendibili.
tls_how_mac | apri il file (Accesso Portachiavi), doppio clic sul certificato > Affidabilità > Autorizza sempre.
tls_how_firefox | Impostazioni > Privacy e sicurezza > Visualizza certificati > Autorità > Importa (oppure usa i certificati di sistema).
tls_names | Nomi e indirizzi nel certificato
tls_names_note | Perché corrisponda l'indirizzo con cui apri l'analizzatore, inseriscilo in DBA_TLS_HOSTS (separato da virgole, nomi e indirizzi IP) e riavvia il container; il certificato viene riemesso e la CA resta la stessa.
mcp_ca | Se l'analizzatore usa HTTPS con una propria CA, scegli anche il certificato della CA come file CA durante l'installazione (download nella pagina HTTPS).
kn_sig | Firma
kn_sig_on | Gli aggiornamenti devono essere firmati con la chiave del progetto (Ed25519)
kn_sig_off | non imposta: solo checksum via HTTPS
account | Account e impostazioni
language | Lingua
live_note | Si aggiorna automaticamente
cfg_link | Impostazioni
cfg_title | Impostazioni
cfg_intro | Modifica qui i valori dell'installazione senza toccare lo stack. Ciò che salvi qui ha la precedenza sulle variabili dello stack.
cfg_general | Generale
cfg_tz | Fuso orario di visualizzazione
cfg_tz_hint | es. Europe/Rome
cfg_hours | Accesso valido (ore)
cfg_kn_url | Indirizzo degli aggiornamenti
cfg_kn_hint | Vuoto per il repository del progetto.
cfg_https | HTTPS
cfg_tls_on | Attiva HTTPS (riavvio necessario)
cfg_tls_hosts | Nomi/indirizzi aggiuntivi nel certificato
cfg_save | Salva
cfg_token | Token API
cfg_token_note | Il token del collegamento IA. Dopo il rinnovo il vecchio non funziona più; un token impostato nello stack torna valido dopo un riavvio, rimuovilo lì.
cfg_token_new | Genera un nuovo token
cfg_password | Cambia password
cfg_pw_current | Password attuale
cfg_pw_new | Nuova password (almeno 10 caratteri)
cfg_pw_again | Ripeti la nuova password
cfg_saved | Salvato.
cfg_restart | Salvato. L'impostazione HTTPS vale dopo il riavvio del container.
cfg_token_done | Nuovo token creato: è sulla pagina del collegamento IA.
cfg_pw_done | Password cambiata.
cfg_err_tz | Fuso orario sconosciuto.
cfg_err_hours | Validità: da 1 a 2160 ore.
cfg_err_url | L'indirizzo deve iniziare con http:// o https://.
cfg_err_hosts | Nome o indirizzo non valido per il certificato.
cfg_err_pw_current | La password attuale non è corretta.
cfg_err_pw_new | Nuova password troppo corta o la ripetizione non coincide.
nav_data | Registrazioni
menu_main | Menu principale
menu_account | Account
menu_connect | Collegamenti
menu_system | Sistema
learn_silent | Nessuna reazione dell'apparecchio (non conteggiate: era acceso?): {}
need_class | Indica tipo, produttore e modello: decidono cosa è generale e cosa è specifico del modello.
analysed | Analizzato
analysed_confirmed | {} % confermato
analysed_of | {} tipi di frame su {} (destinazione + comando) sono spiegati dalla specifica o da un risultato accettato ({} confermati).
open_device | Apri apparecchio
onb_run | Registrare un ciclo completo (avviare un programma e lasciarlo finire)
onb_mcp | Collegare Claude (connessione IA) e fargli analizzare il ciclo
mcp_prompts_title | Prompt per l'analisi
mcp_prompts_intro | Copia un prompt in Claude e sostituisci le parti tra parentesi angolari. Più precisi sono gli orari, più affidabile è la risposta.
mcp_prompt_device | Apparecchio negli esempi
mcp_device_ph | <apparecchio>
mcp_p1_title | Panoramica
mcp_p1 | Usa il Device Bus Analyzer per darmi una panoramica dell'apparecchio «{}»: quali cicli ci sono, quali comandi compaiono e quali sono ancora sconosciuti secondo la specifica?
mcp_p2_title | Analizzare un ciclo con le mie azioni
mcp_p2 | Analizza l'ultimo ciclo completo di «{}». Durante il ciclo ho fatto quanto segue (ora – azione, una per riga): <...>. Quali byte cambiano in linea con le mie azioni e con quale certezza (ripetizioni, rumore del bus)?
mcp_p3_title | Trovare i valori del display
mcp_p3 | Cerca nei cicli di «{}» valori che corrispondano al tempo residuo o alla temperatura sul display. Ho letto questi valori (ora – valore): <...>. Indica comando, posizione del byte, codifica e fattore.
mcp_p4_title | Interpretare i comandi sconosciuti
mcp_p4 | Quali comandi di «{}» sono sconosciuti ma frequenti? Proponi un significato per i tre più frequenti e motivalo con i loro valori nei cicli.
mcp_p5_title | Condividere i risultati (file di contributo)
mcp_p5 | Riassumi i risultati affidabili su «{}» in un file di contributo nel formato della cartella contributions/ del progetto (tipo, produttore, modello, risultati con posizione del byte e stato). Niente frame, timestamp, indirizzi o chiavi.
mcp_p6_title | Condividere un ciclo completo
mcp_p6 | Esporta il ciclo <n.> di «{}» come CSV: tempo in secondi dall'inizio del ciclo, destinazione, comando e dati (hex), più programma e tipo, produttore e modello. Niente nomi host, indirizzi IP o chiavi.
bus_system | Sistema bus
bus_note | Preimpostato in base al produttore. Cambialo se il tuo apparecchio usa un altro bus; è fisso una volta creato l'apparecchio.
login_expired | La pagina di accesso è rimasta aperta troppo a lungo. Inserisci di nuovo la password.
"""
