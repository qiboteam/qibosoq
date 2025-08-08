Usage instructions
==================

After the installation, there are several configuration parameter that one could want to change (IP address of the server, port of the server, path of logs...).
These changes can be done with enviromental variables.
A list of the configurable variables (with values set to the default ones) is the following:

.. code-block:: bash

   # server address
   export QIBOSOQ_HOST=192.168.0.81
   # server port
   export QIBOSOQ_PORT=6000
   # main logger path
   export QIBOSOQ_MAIN_LOGGER_FILE=/home/xilinx/logs/qibosoq.log
   # main logger name
   export QIBOSOQ_MAIN_LOGGER_NAME=qibosoq_logger
   # program logger path
   export QIBOSOQ_PROGRAM_LOGGER_FILE=/home/xilinx/logs/program.log
   # program logger name
   export QIBOSOQ_PROGRAM_LOGGER_NAME=qick_logger
   # bitsream path
   export QIBOSOQ_BITSTREAM=/usr/local/share/pynq-venv/lib/python3.10/site-packages/qick/qick_111.bit
   # is the readout multiplexed?
   export QIBOSOQ_IS_MULTIPLEXED=False
   # is an external clock used as a reference?
   export QIBOSOQ_EXT_CLK=False

.. note::

    Boolean values in the configuration should be written in string form: True/False.

Running the server
""""""""""""""""""

To run the server:

.. code-block:: bash

    nohup sudo -E python -m qibosoq &
    sudo -E python -m qibosoq  # or with on-screen output

To close the server you will need to find the PID of the process (present in the second line of the log file) and:

.. code-block:: bash

    sudo kill PID

Useful aliases
""""""""""""""

We suggest to add to your ``.bashrc`` some aliases to speed up the process.

.. warning::
    Note that with ``server-run-bkg`` the sudo password is not requested, but if the shell does not have sudo privileges it will fail.

Some examples are:

.. code-block:: bash

    alias server-run-bkg="nohup sudo -E python -m qibosoq &"  # run the server in detached mode
    alias server-pid="cat /home/xilinx/logs/qibosoq.log | head -2 | tail -1 | awk '{print \$9}'"  # prints PID

    # print PID of server running in bkg (if it is running)
    serverinfo () {
      num=$(sudo netstat -lnp | grep 6000 | wc -l)

      if [ $num == 1 ]
      then
          echo "Server running at PID $(server-pid)"
      else
          echo "No running server"
      fi
    }

    # close the server running in bkg (if it is running)
    serverclose () {
      num=$(sudo netstat -lnp | grep 6000 | wc -l)

      if [ $num == 1 ]
      then
          echo "Closing server"
          sudo kill $(server-pid)
      else
          echo "No running server"
      fi
    }

External clock reference
""""""""""""""""""""""""

It is possible to provide an external clock reference to the board, allowing all clocks to be synchronized with other instruments.

- For the **RFSoC4x2**, connect a 10 MHz reference to the **CLK_IN** SMA input.
- For the **ZCU111**, provide a 12.8 MHz reference on **External_REF_CLK**.
- For the **ZCU216**, supply a 10 MHz reference to **INPUT_REF_CLK**.

Note that, for the external reference to be detected, the environment variable `QIBOSOQ_EXT_CLK` must be set to `True`.
