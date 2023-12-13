Installation instructions
=========================

``Qibosoq`` is fully compatible with Python >=3.8, <3.12.

Installing with pip
"""""""""""""""""""

This is the raccomended approach in order to install ``Qibosoq``.

.. code-block:: bash

    pip install qibosoq

.. warning::
    For running qibosoq on board, sudo privileges are required, so the installation must be done with:
.. code-block:: bash

    sudo -i python -m pip install qibosoq

Installing from source
""""""""""""""""""""""

In order to install ``qibosoq`` from source, you have to clone the GitHub repository with:

.. code-block:: bash

    git clone https://github.com/qiboteam/qibosoq.git
    cd qibosoq

Now the installation can be done in normal mode or in developer mode (using ``poetry``):

.. code-block:: bash

    pip install .  # normal mode
    poetry install  # developer mode

.. warning::
    For running qibosoq on board, sudo privileges are required, so the installation must be done with:
.. code-block:: bash

    sudo -E python -m pip install <path_to_qibosoq>  # normal mode
    sudo -E python -m poetry install <path_to_qibosoq> # developer mode
