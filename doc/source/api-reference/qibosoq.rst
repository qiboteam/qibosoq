.. _generalpurpose:

Configuration
"""""""""""""

.. autodata:: qibosoq.configuration.HOST
.. autodata:: qibosoq.configuration.PORT
.. autodata:: qibosoq.configuration.MAIN_LOGGER_FILE
.. autodata:: qibosoq.configuration.MAIN_LOGGER_NAME
.. autodata:: qibosoq.configuration.PROGRAM_LOGGER_FILE
.. autodata:: qibosoq.configuration.PROGRAM_LOGGER_NAME
.. autodata:: qibosoq.configuration.QICKSOC_LOCATION
.. autodata:: qibosoq.configuration.IS_MULTIPLEXED

Programs
""""""""

.. autoclass:: qibosoq.programs.base.BaseProgram
    :members:
    :member-order: bysource

.. autoclass:: qibosoq.programs.flux.FluxProgram
    :members:
    :member-order: bysource

.. autoclass:: qibosoq.programs.pulse_sequence.ExecutePulseSequence
    :members:
    :member-order: bysource

.. autoclass:: qibosoq.programs.sweepers.ExecuteSweeps
    :members:
    :member-order: bysource

Server
""""""

.. autoclass:: qibosoq.rfsoc_server.ConnectionHandler
    :members:
    :member-order: bysource

Components
""""""""""

.. autoclass:: qibosoq.components.Config
    :members:
    :member-order: bysource

.. autoclass:: qibosoq.components.OperationCode
    :members:
    :member-order: bysource

.. autoclass:: qibosoq.components.Qubit
    :members:
    :member-order: bysource

.. autoclass:: qibosoq.components.Pulse
    :members:
    :member-order: bysource

.. autoclass:: qibosoq.components.Parameter
    :members:
    :member-order: bysource

.. autoclass:: qibosoq.components.Sweeper
    :members:
    :member-order: bysource

Loggers
"""""""

.. autofunction:: qibosoq.log.configure_logger

.. autofunction:: qibosoq.log.define_loggers
