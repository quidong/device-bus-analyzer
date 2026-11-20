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
bad | error CRC
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
companion | Acompañante
cp_title | Acompañante
cp_intro | Colócate junto al aparato e indica a la app lo que haces. Cada acción se mide en el servidor y se compara con el tráfico del bus. No se envía nada al aparato.
cp_tip | Consejo: deja el aparato en reposo unos dos minutos antes de empezar, para que el análisis sepa qué valores cambian solos.
cp_guided | Comprobaciones guiadas
cp_guided_hint | Cada paso se cronometra de «Ya» a «Hecho», así que tu tiempo de reacción no importa.
cp_free | Marcar una acción
cp_menu_label | Menú / pantalla (opcional)
cp_menu_hint | ¿En qué parte del menú estás? Se guarda con cada acción.
cp_go | Ya
cp_done | Hecho
cp_abort | Parar
cp_step | Paso {} de {}
cp_round | Ronda {}
cp_doing | Hazlo ahora y pulsa Hecho.
cp_note_label | ¿Qué muestra la pantalla / qué opción?
cp_note_needed | Introdúcelo primero.
cp_hint_none | Aún no se ve nada inusual en el bus.
cp_hint_some | Se ven {} cambio(s) inusual(es) en el bus.
cp_hint_nobase | Aún hay pocos datos en reposo para juzgar.
cp_finished | Todos los pasos hechos.
cp_results | Ver resultados
cp_recent | Marcado recientemente
cp_custom | Otra acción
cp_custom_label | ¿Qué has hecho?
cp_add | Marcar
cp_empty | Aún no hay nada marcado.
cp_remove | Quitar
cp_error | No ha funcionado. ¿Inicias sesión de nuevo?
cp_tap_note | Introduce el detalle y pulsa Marcar.
cp_duration | {} s
learn | Aprendido
learn_title | Lo que dice el bus
learn_intro | Para cada acción se comparan los bytes de antes y después. Un byte cuenta cuando cambia una y otra vez con la misma acción y no cambia por sí solo. Las acciones opuestas (abierta / cerrada) deben devolver el mismo byte a su valor.
learn_none | Aún no hay acciones marcadas. Abre el acompañante y marca lo que haces.
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
open_companion | Abrir el acompañante
not_accepted | Aún no hay suficiente evidencia
times | veces
of_n | de
cp_what | Acción
state_now | Ahora
values_title | Valores de la pantalla
values_intro | Estos bytes siguen los números que lees en la pantalla (tiempo restante, temperatura). Acepta uno para ver el valor en las listas de telegramas y en el dispositivo.
encoding | Formato
unit | Unidad
display_value | Valor de la pantalla
need_readings | Lee la pantalla al menos cuatro veces con valores distintos (comprobación guiada «Leer la pantalla»).
spec_suggestion | Propuesta de especificación (YAML)
ha_title | Home Assistant
ha_intro | Todo lo que enseñaste a la app, como valores actuales para Home Assistant. Home Assistant los lee de este servidor con el token de API; nunca se contacta con el aparato.
ha_none | Aún no se ha enseñado nada. Acepta primero hallazgos o valores de pantalla en la página Aprendido.
ha_now | Ahora
ha_step1 | Pon el token de API en secrets.yaml como dba_bearer (valor: Bearer y el token).
ha_step2 | Añade el YAML de abajo a configuration.yaml y reinicia o recarga Home Assistant.
help_link | Ayuda
backup_link | Copia de seguridad
help_title | Cómo grabar un buen ciclo
help_intro | Unos minutos de cuidado junto al aparato hacen fiables los hallazgos.
help_step1 | Crea el dispositivo (tipo, fabricante, modelo) y flashea el firmware recomendado. Espera a que la tarjeta del dispositivo muestre datos.
help_step2 | Abre el acompañante e inicia una comprobación guiada, por ejemplo puerta abierta y cerrada. Haz cada acción en el aparato justo cuando la app lo pida.
help_step3 | Repite cada acción al menos tres veces, con unos segundos de pausa entre ellas. Las repeticiones convierten una suposición en un hallazgo confirmado.
help_step4 | Para ciclos de programa: inicia el marcador, pulsa el botón del aparato y pulsa Hecho en cuanto reaccione. Un marcador por pulsación.
help_step5 | Para valores de pantalla: lee la pantalla e introdúcela cinco veces mientras cambia (tiempo restante, temperatura).
help_step6 | Abre Aprendido, revisa las propuestas y acepta las que coincidan con lo que viste. Las propuestas erróneas se pueden borrar de nuevo.
help_step7 | Exporta los hallazgos: no contienen telegramas, horas, direcciones ni claves y se pueden enviar al proyecto.
help_why_title | ¿Por qué tanto cuidado?
help_why | La app solo escucha. Compara los bytes de antes y después de tu acción con el ruido normal del bus; una buena sincronización y las repeticiones hacen fiable esa comparación.
help_share_title | Compartir
help_share | Usa la exportación de la página Aprendido, o la propuesta de especificación, y añade el archivo en contributions/ del repositorio del proyecto.
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
onb_marker | Grabar una acción en el acompañante
onb_learned | Aceptar un hallazgo en la página Aprendido
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
cp_rest | No toques nada: se mide el ruido propio del aparato.
cp_wait | Faltan {} s
account | Cuenta y ajustes
language | Idioma
live_note | Se actualiza automáticamente
cp_check | Comprobación guiada: {}
cp_waiting | Espera: no toques nada
cp_phase_rest | Midiendo el reposo
cp_manual | Marcar manualmente
cp_manual_hint | Para observaciones libres en el aparato. Consejo: deja el aparato en reposo unos dos minutos antes, para que el análisis sepa qué valores cambian solos.
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
"""
