# BSH D-Bus findings

The authoritative, machine-readable findings live in `src/device_bus_analyzer/spec/bshdbus.yaml`
(also shown in the frontend under "Findings"). Frame layout and CRC are described in the module docstring of
`protocols/bshdbus.py`. Observed so far on a Neff S413K60S0E: program selection, options, remaining time, door and
start sequence; the end-of-run state and the delayed-start payload are still open (status `unknown`/`assumed`).
