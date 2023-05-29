Usage instructions
==================

After the installation, in ``<qibosoq-folder>/src/qibosoq`` you will find the ``configuration.py`` file.
Here, various qibosoq parameter are hardcoded and modifiable (if you installed qibosoq in developer mode).

.. code-block::

    # Server address
    HOST = "192.168.0.72"
    # Port of the server
    PORT = 6000

    # Main logger configuration
    MAIN_LOGGER_FILE = "/home/xilinx/logs/qibosoq.log"
    MAIN_LOGGER_NAME = "qibosoq_logger"
    # Program logger configuration
    PROGRAM_LOGGER_FILE = "/home/xilinx/logs/program.log"
    PROGRAM_LOGGER_NAME = "qick_program"

    # Position of the used bitsream
    QICKSOC_LOCATION = "/home/xilinx/jupyter_notebooks/qick_111_rfbv1_mux.bit"
    IS_MULTIPLEXED = True

Running the server
""""""""""""""""""

To run the server:

.. code-block::

    nohup sudo -i python -m qibosoq &

To close the server you will need to find the PID of the process (present in the second line of the log file) and:

.. code-block::

    sudo kill PID

Useful aliases
""""""""""""""

We suggest to add to your ``.bashrc`` some aliases to speed up the process.
(Note that with ``server-run-bkg`` the sudo password is not requested, but if the shell does not have sudo privileges it will fail.)
Some examples are:

.. code-block::

    alias server-run-bkg="nohup sudo -i python -m qibosoq &"  # run the server in detached mode
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
