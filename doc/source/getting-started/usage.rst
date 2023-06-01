Usage instructions
==================

After the installation, there are several configuration parameter that one could want to change (IP address of the server, port of the server, path of logs...).
These changes can be done with enviromental variables.
A list of the configurable variables (with values set to the default ones) is the following:

.. code-block::

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
   export QIBOSOQ_BITSTREAM=/home/xilinx/jupyter_notebooks/qick_111_rfbv1_mux.bit
   # is the readout multiplexed?
   export QIBOSOQ_IS_MULTIPLEXED=True


Running the server
""""""""""""""""""

To run the server:

.. code-block::

    nohup sudo -E python -m qibosoq &

To close the server you will need to find the PID of the process (present in the second line of the log file) and:

.. code-block::

    sudo kill PID

Useful aliases
""""""""""""""

We suggest to add to your ``.bashrc`` some aliases to speed up the process.
(Note that with ``server-run-bkg`` the sudo password is not requested, but if the shell does not have sudo privileges it will fail.)
Some examples are:

.. code-block::

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
