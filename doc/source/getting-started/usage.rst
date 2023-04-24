Usage instructions
==================

After the installation, in ``<qibosoq-folder>/src/qibosoq`` you will find the ``__main__.py`` file.
Here, the IP and port of the server are hardcoded and modifiable (if you installed qibosoq in developer mode).

.. code-block::

    HOST = "192.168.0.72"   # Server address
    PORT = 6000             # Port to listen on

Attached Mode
"""""""""""""

To run the server in attached mode, with the log output directly on the terminal, you can use:

.. code-block::

    sudo -i python -m qibosoq

This mode is useful for debugging, but comes with the disadvantage of being attached to a specific terminal session: when you will close the terminal, the server will be closed too.
Eventually, the server can be closed also with <Ctrl-C>.

Detatched Mode
""""""""""""""

To avoid it, you can use qibosoq in detached mode, redirecting the output to a log file:

.. code-block::

    nohup sudo -i python -m qibosoq > logs/mylog &

To close the server you will need to find the PID of the process (present in the second line of the log file) and:

.. code-block::

    sudo kill PID

Useful aliases
""""""""""""""

We suggest to add to your ``.bashrc`` some aliases to speed up the process. Some examples are:

.. code-block::

    alias server-run="sudo -i python -m qibosoq"  # run the server in attached mode
    alias server-run-bkg="nohup sudo -i python -m qibosoq > logs/mylog &"  # run the server in detached mode
    alias server-info="cat logs/mylog | head -2 | tail -1 | awk '{print \$3 \" \" \$4}'"  # prints PID
    alias server-close="sudo kill $(cat logs/mylog | head -2 | tail -1 | awk '{print $4}')"  # close the server running in bkg
