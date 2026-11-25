"""Spanish UI strings (key | text); the key set must equal the English one (checked by a test)."""
RAW = """
title | Device Bus Analyzer
login | Iniciar sesión
email | Correo electrónico
password | Contraseña
logout | Cerrar sesión
bad_login | Correo o contraseña incorrectos.
locked | Demasiados intentos; inténtalo de nuevo en unos minutos.
sources | Fuentes
frames | Tramas
timeline | Cronología
commands | Comandos
bursts | Ráfagas en bruto
findings | Hallazgos
quality | Calidad
name | Nombre
protocol | Protocolo
first | Primero
last | Último
time | Hora
dest | Destino
cmd | Cmd
data | Datos
ack | ACK
crc | CRC
decoded | Decodificado
status | Estado
filter | Filtrar
since | Desde
until | Hasta
limit | Límite
only_bad | Solo errores CRC
count | Cantidad
distinct | Valores distintos
evidence | Evidencia
no_data | Aún no hay datos.
gaps | Huecos / pérdidas
sessions | Arranques
ok | válida
bad | puntos dañados (CRC)
not_repeated | de ellos no repetidos intactos
raw_data | con datos brutos (RAW1)
legacy_data | grabación antigua sin datos brutos
values | Valores
confirmed | confirmado
assumed | supuesto
unknown | desconocido
next | Siguiente
prev | Anterior
burst_hex | Hex en bruto
runs | Ciclos
run | Ciclo
start | Inicio
end | Fin
duration | Duración
program | Programa
remaining | Restante
running | en marcha
runs_note | Un ciclo se deduce: empieza con el comando de inicio y termina en el último telegrama antes de un silencio. Ambos se marcan como supuestos.
sender | Emisor
receiver | Receptor
nodes | Nodos
sender_note | La trama solo lleva el destino; el emisor se deduce de él y como mucho es supuesto.
devices | Dispositivos
address | Dirección
device | Dispositivo
devices_note | Las direcciones de origen y destino se leen de la trama y son siempre ciertas; lo que es un dispositivo se deduce de su tráfico y lleva un estado.
timezone_note | Horas en
all | todos
devices_title | Dispositivos
new_device | Nuevo dispositivo
edit | Editar
save | Guardar
cancel | Cancelar
device_type | Tipo
manufacturer | Fabricante
model | Modelo
host | Host / IP
port | Puerto
api_key | Clave de cifrado de la API
key_set | definida
key_missing | no definida
key_keep | Déjalo vacío para conservar la clave guardada.
key_clear | Eliminar la clave guardada
enabled | Recopilar
disabled | en pausa
enabled_on | recopilando
unclassified | sin clasificar
import_only | solo importación
connection | Conexión
dev_note | Los dispositivos se guardan en el volumen de la base de datos. El nombre y el decodificador no se pueden cambiar una vez creado el dispositivo.
pick_hint | Elige una sugerencia o escribe tu propio valor.
protocol_fixed | El protocolo queda fijado al crear el dispositivo.
bad_name | Nombre: solo letras, cifras, - y _ (máx. 40).
bad_protocol | Protocolo desconocido.
bad_host | Falta el host o no es válido.
bad_port | El puerto debe estar entre 1 y 65535.
bad_key | La clave debe ser la clave base64 de la API de ESPHome (32 bytes).
exists | Ya existe un dispositivo con este nombre.
bad_input | Entrada no válida, o el nombre ya se usa con otro protocolo.
confirm_mismatch | El nombre no coincide. No se ha borrado nada.
delete | Borrar
delete_title | Borrar dispositivo
delete_confirm_label | Escribe el nombre para confirmar
delete_forever | Borrar definitivamente
delete_warn | Esto elimina de forma permanente el dispositivo y todo lo registrado de él. No se puede deshacer.
delete_removes | Se eliminará:
n_bursts | ráfagas en bruto
n_frames | tramas
n_heartbeats | latidos
n_sessions | arranques de la placa
n_gaps | entradas de huecos
delete_keep | Los demás dispositivos no se tocan.
firmware | Firmware
fw_title | Firmware ESPHome
copy | Copiar
copied | Copiado
download | Descargar
back | Atrás
close | Cerrar
fw_intro | Archivos ESPHome recomendados para esta familia de dispositivos. Flashea una placa con ellos y luego introduce su host y su clave de API en Dispositivos.
fw_step1 | En ESPHome Device Builder crea un dispositivo y pega el YAML (si hay un segundo archivo, ponlo al lado).
fw_step2 | Guarda claves y contraseñas en secrets.yaml; usa la clave de cifrado de API generada para este dispositivo.
fw_step3 | Flashea la placa y añade aquí el dispositivo (Dispositivos > Nuevo dispositivo).
device_saved | Dispositivo guardado. Este es el firmware que le corresponde:
to_devices | Volver a los dispositivos
other | Otro …
other_maker | Nombre del fabricante
other_type | Tipo
decoder | Decodificador
decoder_note | El decodificador depende del fabricante y queda fijado al crear el dispositivo.
key_never | Solo se guarda, nunca se vuelve a mostrar.
needs_class | Tipo y modelo aún sin asignar.
assign | Asignar
st_live | recopilando
st_waiting | esperando al dispositivo
st_paused | en pausa
st_import | solo importación
last_seen | Visto por última vez
never | nunca
pause | Pausar
resume | Reanudar
wz_next | Continuar
step_of | Paso
which_type | ¿Qué tipo de dispositivo?
which_maker | ¿Qué fabricante?
which_model | ¿Qué modelo?
which_conn | ¿Cómo está conectado?
firmware_link | Ver firmware
ago | hace {}
s | s
min | min
h | h
d | d
menu | Navegación
more | Más
choose | Elige una opción.
model_hint | Sugerencias del catálogo. Tus propios valores se ofrecerán de nuevo la próxima vez.
brand_other_note | Otros fabricantes requieren elegir un decodificador.
cp_duration | {} s
learn | Aprendido
learn_title | Lo que dice el bus
learn_intro | Para cada acción se comparan los bytes de antes y después. Un byte cuenta cuando cambia una y otra vez con la misma acción y no cambia por sí solo. Las acciones opuestas (abierta / cerrada) deben devolver el mismo byte a su valor.
learn_none | No hay acciones registradas para este aparato.
learn_few_base | Hay muy poco tiempo en reposo en la grabación para distinguir ruido de efecto. Deja el aparato en reposo un par de minutos y repite.
learn_stats | {} acciones, {} telegramas, {} ventanas en reposo
hits | Aciertos
change | Cambio
noise | Ruido
byte | Byte
accept | Aceptar
meaning | Significado
learned_title | Hallazgos aceptados
learned_none | Aún no se ha aceptado nada.
export | Exportar hallazgos
export_note | La exportación contiene solo lo que aceptaste: direcciones, posiciones de byte, valores y el modelo del aparato. Sin telegramas, horas, nombres de host ni claves.
no_candidates | Ningún byte cambió de forma fiable con esta acción.
events_title | Telegramas vistos solo con esta acción
actions | Acciones
not_accepted | Aún no hay suficiente evidencia
times | veces
of_n | de
state_now | Ahora
values_title | Valores de la pantalla
values_intro | Estos bytes siguen los números que lees en la pantalla (tiempo restante, temperatura). Acepta uno para ver el valor en las listas de telegramas y en el dispositivo.
encoding | Formato
unit | Unidad
display_value | Valor de la pantalla
spec_suggestion | Propuesta de especificación (YAML)
ha_title | Home Assistant
ha_intro | Todo lo que enseñaste a la app, como valores actuales para Home Assistant. Home Assistant los lee de este servidor con el token de API; nunca se contacta con el aparato.
ha_none | Aún no se ha enseñado nada. Acepta primero hallazgos o valores de pantalla en la página Aprendido.
ha_now | Ahora
ha_step1 | Pon el token de API en secrets.yaml como dba_bearer (valor: Bearer y el token).
ha_step2 | Añade el YAML de abajo a configuration.yaml y reinicia o recarga Home Assistant.
help_link | Ayuda
backup_link | Copia de seguridad
help_title | De la grabación al hallazgo
help_intro | La aplicación solo graba y decodifica lo que ya conoce. El análisis lo hace Claude a través de la conexión IA (MCP).
help_step1 | Crea el aparato. Tipo, fabricante y modelo son obligatorios, porque deciden qué es general y qué es específico del modelo. Graba el firmware recomendado y espera a que la tarjeta muestre datos.
help_step2 | Graba ciclos completos: elige un programa, inícialo y deja que termine. Apunta lo que haces en el aparato y cuándo (p. ej. «20:14 puerta abierta»).
help_step3 | Repite las acciones interesantes varias veces con unos segundos de pausa. Las repeticiones convierten una suposición en un hallazgo confirmado.
help_step4 | Conecta Claude: menú de cuenta → Conexión IA. Instala la extensión e introduce la dirección y el token de API.
help_step5 | Deja que Claude analice el ciclo. Hay prompts de ejemplo en la página Conexión IA; añade tus notas con la hora.
help_step6 | «Analizado» en la tarjeta del aparato muestra cuántas tramas explica ya la especificación o un hallazgo aceptado.
help_step7 | Comparte lo que hayas averiguado con el proyecto (ver abajo), para que los siguientes empiecen con más conocimiento.
help_why_title | ¿Por qué tanto cuidado?
help_why | La aplicación solo escucha y nunca envía nada al aparato. Claude compara las tramas con tus notas y la especificación existente; horas exactas y repeticiones hacen fiable la comparación.
help_share_title | Compartir con el proyecto
help_share | Hay dos caminos. O bien aportar ciclos completos: Claude exporta un ciclo con tiempos relativos al inicio y sin nombres de host, direcciones ni claves, y lo adjuntas a un issue. O bien compartir hallazgos analizados: Claude escribe un archivo de contribución para contributions/ (tipo, fabricante, modelo, posiciones de bytes con estado; sin tramas, horas, direcciones ni claves). La CI comprueba cada archivo.
backup_title | Copia de seguridad
backup_download | Descargar una copia de seguridad
backup_download_intro | Una copia consistente de todos los dispositivos, telegramas, marcadores y hallazgos en un solo archivo.
backup_keys_warning | El archivo contiene las claves ESPHome guardadas. Manténlo en privado.
backup_download_btn | Descargar copia
backup_restore | Restaurar una copia de seguridad
backup_restore_intro | Sustituye todo en esta instalación por el contenido del archivo. La copia de seguridad previa solo se conserva mientras dura la restauración, así que descarga antes una copia.
backup_file | Archivo de copia
backup_confirm | Escribe RESTORE para confirmar
backup_restore_btn | Restaurar
backup_restored | Copia restaurada.
backup_err_confirm_mismatch | Escribe RESTORE para confirmar.
backup_err_not_sqlite | No es un archivo de copia válido.
backup_err_integrity | El archivo está dañado.
backup_err_missing_tables | El archivo no es una copia de Device Bus Analyzer.
backup_err_too_big | El archivo es demasiado grande.
onb_title | Primeros pasos
onb_device | Crear un dispositivo
onb_data | Recibir los primeros telegramas
mcp_link | Conexión con IA
mcp_title | Conexión con IA (MCP)
mcp_intro | Para que Claude pueda leer y analizar tus grabaciones necesita la extensión y dos datos: la dirección de esta instalación y el token de API. La extensión solo lee y nunca envía nada a un dispositivo.
mcp_step1 | Descarga la extensión y ábrela con doble clic (Claude Desktop pide confirmar la instalación).
mcp_step2 | Durante la instalación introduce la dirección y el token de API de abajo.
mcp_download | Descargar extensión (.mcpb)
mcp_url | Dirección de esta instalación
mcp_url_note | La dirección debe ser accesible desde el ordenador donde corre Claude. Se toma del navegador; si usas localhost, introduce la dirección de la red local.
mcp_token | Token de API
mcp_token_show | Mostrar token
mcp_token_warn | El token da acceso de lectura a todas las grabaciones. No lo compartas.
mcp_token_none | Aún no hay token de API. Define DBA_API_TOKEN en el contenedor y reinícialo.
mcp_other | Claude Code
mcp_other_note | El servidor se ejecuta localmente con Node (stdio). Ajusta la ruta a la carpeta extension/ del repositorio:
mcp_local_title | Solo para uso local
mcp_local | La conexión está pensada para uso local y solo funciona con Claude (Claude Desktop y Claude Code). El analizador no se publica en internet; la extensión se ejecuta en tu ordenador y lee a través de la red local. Otros servicios de IA como ChatGPT no son compatibles.
copy_cmd | Copiar comando
kn_link | Conocimiento de dispositivos
kn_title | Actualizar el conocimiento de dispositivos
kn_intro | Los hallazgos de protocolo, el catálogo de dispositivos y el firmware recomendado proceden del proyecto de GitHub y se pueden actualizar sin una imagen de contenedor nueva. Los datos grabados no se tocan; la decodificación usa de inmediato el nuevo estado.
kn_active | Versión activa
kn_bundled | Incluida en la imagen
kn_src_update | actualización descargada
kn_src_bundled | incluida
kn_last | Última comprobación
kn_never | nunca
kn_check | Comprobar ahora
kn_auto | Comprobar automáticamente cada día
kn_save | Guardar
kn_reset | Volver a la versión incluida
kn_res_updated | Actualizado a
kn_res_current | Ya está actualizado.
kn_res_error | Error
kn_res_needs_app_update | La actualización necesita una versión más nueva de la app (imagen nueva).
kn_note | Solo se descargan archivos de datos (YAML), se comprueban y se activan solo si todo es válido. El contenedor necesita acceso HTTPS saliente a GitHub.
backup_err_active_content | El archivo contiene disparadores o vistas y no se restaura por motivos de seguridad.
tls_link | HTTPS
tls_title | HTTPS en la red local
tls_intro | El analizador usa HTTPS con un certificado de su propia autoridad certificadora (CA) local. Instala el certificado de la CA una vez en tus dispositivos y desaparece la advertencia del navegador.
tls_state | Conexión
tls_not_https | esta página se cargó sin cifrar
tls_hosts | Válido para
tls_expires | Caduca
tls_fp | Huella de la CA (SHA-256)
tls_download | Descargar el certificado de la CA
tls_no_ca | No hay CA local: HTTPS está desactivado o usa tu propio certificado.
tls_how | Instalar el certificado de la CA
tls_how_ios | descarga el archivo, instala el perfil en Ajustes y actívalo en General > Información > Ajustes de confianza de certificados.
tls_how_android | Ajustes > Seguridad > Cifrado y credenciales > Instalar un certificado > Certificado de CA.
tls_how_windows | haz doble clic en el archivo > Instalar certificado > Equipo local > Entidades de certificación raíz de confianza.
tls_how_mac | abre el archivo (Acceso a Llaveros), haz doble clic en el certificado > Confianza > Confiar siempre.
tls_how_firefox | Ajustes > Privacidad y seguridad > Ver certificados > Autoridades > Importar (o usar los certificados del sistema).
tls_names | Nombres y direcciones en el certificado
tls_names_note | Para que coincida la dirección con la que abres el analizador, indícala en DBA_TLS_HOSTS (separada por comas, nombres y direcciones IP) y reinicia el contenedor; el certificado se vuelve a emitir y la CA no cambia.
mcp_ca | Si el analizador usa HTTPS con su propia CA, selecciona también el certificado de la CA como archivo de CA durante la instalación (descarga en la página HTTPS).
kn_sig | Firma
kn_sig_on | Las actualizaciones deben estar firmadas con la clave del proyecto (Ed25519)
kn_sig_off | no exigida: solo sumas de verificación por HTTPS
account | Cuenta y ajustes
language | Idioma
live_note | Se actualiza automáticamente
cfg_link | Ajustes
cfg_title | Ajustes
cfg_intro | Cambia aquí los valores de la instalación sin editar el stack. Lo guardado aquí prevalece sobre las variables del stack.
cfg_general | General
cfg_tz | Zona horaria de visualización
cfg_tz_hint | p. ej. Europe/Madrid
cfg_hours | Sesión válida (horas)
cfg_kn_url | Dirección de las actualizaciones
cfg_kn_hint | Vacío para el repositorio del proyecto.
cfg_https | HTTPS
cfg_tls_on | Activar HTTPS (requiere reinicio)
cfg_tls_hosts | Nombres/direcciones adicionales en el certificado
cfg_save | Guardar
cfg_token | Token de API
cfg_token_note | El token de la conexión de IA. Al renovarlo el anterior deja de funcionar; un token definido en el stack vuelve a valer tras un reinicio, quítalo allí.
cfg_token_new | Generar un token nuevo
cfg_password | Cambiar contraseña
cfg_pw_current | Contraseña actual
cfg_pw_new | Contraseña nueva (mínimo 10 caracteres)
cfg_pw_again | Repite la contraseña nueva
cfg_saved | Guardado.
cfg_restart | Guardado. El ajuste de HTTPS se aplica tras reiniciar el contenedor.
cfg_token_done | Token nuevo creado: aparece en la página de conexión de IA.
cfg_pw_done | Contraseña cambiada.
cfg_err_tz | Zona horaria desconocida.
cfg_err_hours | Validez: de 1 a 2160 horas.
cfg_err_url | La dirección debe empezar por http:// o https://.
cfg_err_hosts | Nombre o dirección no válidos para el certificado.
cfg_err_pw_current | La contraseña actual no es correcta.
cfg_err_pw_new | Contraseña nueva demasiado corta o la repetición no coincide.
nav_data | Grabaciones
menu_main | Menú principal
menu_account | Cuenta
menu_connect | Conexiones
menu_system | Sistema
learn_silent | Sin reacción del aparato (no contadas, ¿estaba encendido?): {}
need_class | Indica tipo, fabricante y modelo: deciden qué es general y qué es específico del modelo.
analysed | Analizado
analysed_of | {} de {} tramas están explicadas por la especificación o un hallazgo aceptado ({} confirmadas).
open_device | Abrir aparato
onb_run | Grabar un ciclo completo (iniciar un programa y dejar que termine)
onb_mcp | Conectar Claude (conexión IA) y dejar que analice el ciclo
mcp_prompts_title | Prompts para el análisis
mcp_prompts_intro | Copia un prompt en Claude y sustituye las partes entre corchetes angulares. Cuanto más exactas tus horas, más fiable la respuesta.
mcp_prompt_device | Aparato en los ejemplos
mcp_device_ph | <aparato>
mcp_p1_title | Visión general
mcp_p1 | Usa el Device Bus Analyzer para darme una visión general del aparato «{}»: ¿qué ciclos hay, qué comandos aparecen y cuáles siguen siendo desconocidos según la especificación?
mcp_p2_title | Analizar un ciclo con mis acciones
mcp_p2 | Analiza el último ciclo completo de «{}». Durante él hice lo siguiente (hora – acción, una por línea): <...>. ¿Qué bytes cambian de acuerdo con mis acciones y con qué seguridad (repeticiones, ruido del bus)?
mcp_p3_title | Encontrar valores de pantalla
mcp_p3 | Busca en los ciclos de «{}» valores que coincidan con el tiempo restante o la temperatura de la pantalla. Leí estos valores (hora – valor): <...>. Indica comando, posición de byte, codificación y factor.
mcp_p4_title | Interpretar comandos desconocidos
mcp_p4 | ¿Qué comandos de «{}» son desconocidos pero aparecen a menudo? Propón un significado para los tres más frecuentes y justifícalo con sus valores a lo largo de los ciclos.
mcp_p5_title | Compartir hallazgos (archivo de contribución)
mcp_p5 | Resume los hallazgos fiables sobre «{}» como archivo de contribución con el formato de la carpeta contributions/ del proyecto (tipo, fabricante, modelo, hallazgos con posición de byte y estado). Sin tramas, marcas de tiempo, direcciones ni claves.
mcp_p6_title | Compartir un ciclo completo
mcp_p6 | Exporta el ciclo <n.º> de «{}» como CSV: tiempo en segundos desde el inicio del ciclo, destino, comando y datos (hex), además de programa y tipo, fabricante y modelo. Sin nombres de host, direcciones IP ni claves.
"""
