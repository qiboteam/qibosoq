# Qibosoq
Repository for developing server side of RFSoC fpga boards
Qibosoq is a server for integrating [Qick](https://github.com/openquantumhardware/qick) in the [Qibolab](https://github.com/qiboteam/qibolab) ecosystem
for executing arbitrary pulses sequences on QPUs.

## Installation

The package can be installed by source:
```sh
git clone https://github.com/qiboteam/qibosoq.git
cd qibosoq
pip install .
```
### Developer instructions
For development make sure to install the package using [`poetry`](https://python-poetry.org/) and to install the pre-commit hooks:
```sh
git clone https://github.com/qiboteam/qibosoq.git
cd qibosoq
poetry install
pre-commit install
```

## Run the server

The simplest way of executing the server is:
```
sudo -i python <absolute-path-to-qibosoq>/src/qibosoq/rfsoc_server.py
```
and the server can be closed with `Ctrl-C`.\
Note that with this command the script will close as soon as the terminal where it's running it's closed.
To run the server in detached mode you can use:

```
sudo -i python <absolute-path-to-qibosoq>/src/qibosoq/rfsoc_server.py > logs/mylog & disown
```
And the server can be closed with `sudo kill PID`.

### TII boards

With TII boards the server can also be executed using `server-run` for normal mode and `server-run-bkg`for detached mode.

## Contributing

Contributions, issues and feature requests are welcome!
Feel free to check
<a href="https://github.com/qiboteam/qibosoq/issues"><img alt="GitHub issues" src="https://img.shields.io/github/issues-closed/qiboteam/qibosoq"/></a>
