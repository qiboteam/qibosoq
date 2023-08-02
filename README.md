# Qibosoq

![Tests](https://github.com/qiboteam/qibosoq/workflows/Tests/badge.svg)
[![codecov](https://codecov.io/gh/qiboteam/qibosoq/branch/main/graph/badge.svg?token=1EKZKVEVX0)](https://codecov.io/gh/qiboteam/qibosoq)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.8083285.svg)](https://doi.org/10.5281/zenodo.8083285)

Repository for developing server side of RFSoC fpga boards
Qibosoq is a server for integrating [Qick](https://github.com/openquantumhardware/qick) in the [Qibolab](https://github.com/qiboteam/qibolab) ecosystem
for executing arbitrary pulses sequences on QPUs.

The complete documentation for can be found at:

* [qibo.science/qibosoq/stable](https://qibo.science/qibosoq/stable/)
* [qibo.science/qibosoq/latest](https://qibo.science/qibosoq/latest/)


## Installation
Please refer to the [documentation](https://qibo.science/qibosoq/stable/getting-started/installation.html) for installation instructions.

## Configuration parameters

In `configuration.py` some default qibosoq parameters are hardcoded. They can be changed using environment variables ([see documentation](https://qibo.science/qibosoq/stable/getting-started/usage.html)).

* IP of the server
* Port of the server
* Paths of log files
* Name of python loggers
* Path of bitstream
* Type of readout (multiplexed or not, depending on the loaded bitstream)

## Run the server

The simplest way of executing the server is:
```
sudo -E python -m qibosoq
```
and the server can be closed with `Ctrl-C`.\
Note that with this command the script will close as soon as the terminal where it's running it's closed.
To run the server in detached mode you can use:

```
nohup sudo -E python -m qibosoq &
```
And the server can be closed with `sudo kill <PID>` (PID will be saved in log).

### TII boards

With TII boards the server can also be executed using the alias `server-run-bkg`.

Also, two additional command are added in `.bashrc`: `serverinfo` and `serverclose`.
`serverinfo` will print the PID if the server is running, otherwise will print "No running server".
`serverclose` will close the server, if it is running.

All these commands require sudo privileges.

## Contributing

Contributions, issues and feature requests are welcome!
Feel free to check
<a href="https://github.com/qiboteam/qibosoq/issues"><img alt="GitHub issues" src="https://img.shields.io/github/issues-closed/qiboteam/qibosoq"/></a>
