# Qibosoq

[![codecov](https://codecov.io/gh/qiboteam/qibosoq/branch/main/graph/badge.svg?token=1EKZKVEVX0)](https://codecov.io/gh/qiboteam/qibosoq)
![PyPI - Version](https://img.shields.io/pypi/v/qibosoq)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/qibosoq)


Repository for developing server side of RFSoC fpga boards
Qibosoq is a server for integrating [Qick](https://github.com/openquantumhardware/qick) in the [Qibolab](https://github.com/qiboteam/qibolab) ecosystem
for executing arbitrary pulses sequences on QPUs.

## Documentation

[![docs](https://github.com/qiboteam/qibosoq/actions/workflows/publish.yml/badge.svg)](https://qibo.science/qibosoq/stable/)

Qibosoq documentation is available [here](https://qibo.science/qibosoq/stable/).


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

## Citation policy
[![arXiv](https://img.shields.io/badge/arXiv-2310.05851-b31b1b.svg)](https://arxiv.org/abs/2310.05851)
[![DOI](https://zenodo.org/badge/567203263.svg)](https://zenodo.org/badge/latestdoi/567203263)



If you use the package please refer to [the documentation](https://qibo.science/qibo/stable/appendix/citing-qibo.html#publications) for citation instructions
