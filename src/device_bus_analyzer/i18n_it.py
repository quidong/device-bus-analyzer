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
only_bad | Solo errori CRC
count | Numero
distinct | Valori distinti
evidence | Evidenza
no_data | Ancora nessun dato.
gaps | Buchi / perdite
sessions | Avvii
ok | valido
bad | errore CRC
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
decoder_note | Il decodificatore dipende dal produttore ed è fisso dopo la creazione del dispositivo.
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
model_hint | Suggerimenti dal catalogo. I tuoi valori verranno riproposti la prossima volta.
brand_other_note | Gli altri produttori richiedono la scelta di un decodificatore.
companion | Assistente
cp_title | Assistente
cp_intro | Mettiti davanti all'apparecchio e dì all'app cosa fai. Ogni azione viene cronometrata sul server e confrontata con il traffico del bus. All'apparecchio non viene inviato nulla.
cp_tip | Suggerimento: lascia l'apparecchio a riposo per circa due minuti prima di iniziare, così l'analisi sa quali valori cambiano da soli.
cp_guided | Verifiche guidate
cp_guided_hint | Ogni passo è cronometrato da «Via» a «Fatto», quindi il tuo tempo di reazione non conta.
cp_free | Segna un'azione
cp_menu_label | Menu / display (facoltativo)
cp_menu_hint | Dove sei nel menu? Viene salvato con ogni azione.
cp_go | Via
cp_done | Fatto
cp_abort | Ferma
cp_step | Passo {} di {}
cp_round | Giro {}
cp_doing | Fallo ora, poi tocca Fatto.
cp_note_label | Cosa mostra il display / quale opzione?
cp_note_needed | Inseriscilo prima.
cp_hint_none | Finora nulla di insolito sul bus.
cp_hint_some | Visti {} cambiamento/i insolito/i sul bus.
cp_hint_nobase | Troppi pochi dati a riposo per giudicare.
cp_finished | Tutti i passi completati.
cp_results | Vedi i risultati
cp_recent | Segnato di recente
cp_custom | Altra azione
cp_custom_label | Cosa hai fatto?
cp_add | Segna
cp_empty | Ancora nulla di segnato.
cp_remove | Rimuovi
cp_error | Non ha funzionato. Accedi di nuovo?
cp_tap_note | Inserisci il dettaglio, poi tocca Segna.
cp_duration | {} s
learn | Appreso
learn_title | Cosa dice il bus
learn_intro | Per ogni azione si confrontano i byte prima e dopo. Un byte conta quando cambia ogni volta con la stessa azione e non cambia da solo. Le azioni opposte (aperto / chiuso) devono riportare lo stesso byte al valore di partenza.
learn_none | Ancora nessuna azione segnata. Apri l'assistente e segna ciò che fai.
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
open_companion | Apri l'assistente
not_accepted | Prove ancora insufficienti
times | volte
of_n | su
cp_what | Azione
state_now | Ora
values_title | Valori dal display
values_intro | Questi byte seguono i numeri che leggi sul display (tempo rimanente, temperatura). Accettane uno per vedere il valore negli elenchi dei telegrammi e sul dispositivo.
encoding | Formato
unit | Unità
display_value | Valore del display
need_readings | Leggi il display almeno quattro volte con valori diversi (verifica guidata «Leggi il display»).
spec_suggestion | Proposta di specifica (YAML)
ha_title | Home Assistant
ha_intro | Tutto ciò che hai insegnato all'app, come valori attuali per Home Assistant. Home Assistant li legge da questo server con il token API; l'apparecchio non viene mai contattato.
ha_none | Ancora nulla di insegnato. Accetta prima risultati o valori del display nella pagina Appreso.
ha_now | Ora
ha_step1 | Inserisci il token API in secrets.yaml come dba_bearer (valore: Bearer e il token).
ha_step2 | Aggiungi lo YAML qui sotto a configuration.yaml e riavvia o ricarica Home Assistant.
help_link | Aiuto
backup_link | Backup
help_title | Come registrare un buon ciclo
help_intro | Pochi minuti di cura davanti all'apparecchio rendono affidabili i risultati.
help_step1 | Crea il dispositivo (tipo, produttore, modello) e flasha il firmware consigliato. Attendi che la scheda del dispositivo mostri dati.
help_step2 | Apri l'assistente e avvia una verifica guidata, ad esempio sportello aperto e chiuso. Esegui ogni azione sull'apparecchio esattamente quando l'app lo chiede.
help_step3 | Ripeti ogni azione almeno tre volte, con qualche secondo di pausa tra l'una e l'altra. Le ripetizioni trasformano un'ipotesi in un risultato confermato.
help_step4 | Per i cicli di programma: avvia il marcatore, premi il tasto sull'apparecchio e tocca Fatto appena reagisce. Un marcatore per ogni pressione.
help_step5 | Per i valori del display: leggi il display e inseriscilo cinque volte mentre cambia (tempo rimanente, temperatura).
help_step6 | Apri Appreso, controlla le proposte e accetta quelle che corrispondono a ciò che hai visto. Le proposte sbagliate si possono eliminare di nuovo.
help_step7 | Esporta i risultati: non contengono telegrammi, orari, indirizzi o chiavi e possono essere inviati al progetto.
help_why_title | Perché tanta cura?
help_why | L'app si limita ad ascoltare. Confronta i byte prima e dopo la tua azione con il normale rumore del bus; tempi precisi e ripetizioni rendono affidabile il confronto.
help_share_title | Condivisione
help_share | Usa l'esportazione nella pagina Appreso, o la proposta di specifica, e aggiungi il file sotto contributions/ nel repository del progetto.
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
onb_marker | Registra un'azione nell'assistente
onb_learned | Accetta un risultato nella pagina Appreso
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
mcp_other | Altri client (Claude Code, Cursor …)
mcp_other_note | Il server gira in locale con Node (stdio). Adatta il percorso alla cartella extension/ del repository:
mcp_chatgpt_title | ChatGPT
mcp_chatgpt | ChatGPT non può usare questa estensione: si collega solo a server HTTPS raggiungibili pubblicamente e supporta OAuth o nessun accesso, non un token API. Una strada sarebbe un accesso remoto con login proprio; non mettere questa installazione su internet senza protezione.
copy_cmd | Copia comando
"""
