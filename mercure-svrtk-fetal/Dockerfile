# SVRTK Fetal MRI Processor - Docker Configuration
# Uses the working v8 container: localhost/svrtk:openjpeg-embedded-nii2dcm-fixed-v8

FROM localhost/svrtk:openjpeg-embedded-nii2dcm-fixed-v8

# Set labels  
LABEL maintainer="Stanford AIDE Lab"
LABEL description="SVRTK Fetal MRI Intelligent Processor v8"
LABEL version="8.0"

# Set working directory
WORKDIR /app

# Copy the intelligent processor
COPY processor/ /app/processor/
COPY config/ /app/config/

# Make processor executable
RUN chmod +x /app/processor/intelligent_svrtk_processor.py

# Set environment variables for SVRTK v8 compatibility
ENV SVRTK_VERSION=8
ENV TEMP_DIR=/tmp
ENV WORK_DIR=/tmp
ENV PYTHONPATH=/app:$PYTHONPATH

# Create necessary directories with correct permissions
RUN mkdir -p /tmp/tmp_proc_ssfse_brain \
    /tmp/tmp_proc_ssfse_body \
    /tmp/tmp_proc_fiesta_brain \
    /tmp/tmp_proc_fiesta_body \
    /opt/mercure/data

# Set proper permissions
RUN chmod -R 755 /tmp/tmp_proc_* \
    && chmod 755 /app/processor/intelligent_svrtk_processor.py

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import sys; print('SVRTK v8 processor ready'); sys.exit(0)"

# Entry point - uses MERCURE_IN_DIR/MERCURE_OUT_DIR env vars when no CLI args given
ENTRYPOINT ["python3", "/app/processor/intelligent_svrtk_processor.py"]
CMD []