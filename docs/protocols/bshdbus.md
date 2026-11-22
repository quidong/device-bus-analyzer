# BSH D-Bus findings

The authoritative, machine-readable findings live in `src/device_bus_analyzer/spec/bshdbus.yaml`
(also shown in the frontend under "Findings"). Frame layout and CRC are described in the module docstring of
`protocols/bshdbus.py`. Observed so far on a Neff S413K60S0E: program selection, options, remaining time, door and
start sequence and the end of a run (`27/2007 = 03`, used as the end marker for run detection). The delayed-start
payload, the program phases (`25/2005`) and the salt / rinse aid bits are still open (status `unknown`/`assumed`).
