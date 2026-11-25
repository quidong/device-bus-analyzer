# Contributions

Findings analysed with Claude (prompt *Share findings* on the AI connection page) or exported from **Learned → Export findings**. One file per appliance model:
`contributions/<protocol>/<manufacturer>-<model>.json`.

They contain only addresses, byte positions, values, a meaning you typed and the device model. No telegrams, times, host names or keys.
Every file here is checked by the CI (`dba validate-contribution`). To turn one into spec entries run `dba suggest-spec <file>`
(or use **Spec suggestion** on the Learned page) and merge the result into `src/device_bus_analyzer/spec/<protocol>.yaml`.
A finding becomes *confirmed* in the spec once several recordings or people agree.
