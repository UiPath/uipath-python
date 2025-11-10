"""
Add this snippet at the beginning of your eval run to see trace export logs.
You can add this to the top of cli_eval.py or run it before your eval.
"""
import logging

# Enable DEBUG logging for the trace exporter
logging.basicConfig(level=logging.WARNING)  # Keep general logging quiet
logging.getLogger('uipath.tracing._otel_exporters').setLevel(logging.DEBUG)

# Add a simple handler if needed
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logging.getLogger('uipath.tracing._otel_exporters').addHandler(handler)

print("✓ Trace export logging enabled")
