ARG FLUTTER_VERSION=3.29.0
FROM ghcr.io/cirruslabs/flutter:${FLUTTER_VERSION}

WORKDIR /capture
COPY scripts/capture.sh /scripts/capture.sh
RUN chmod +x /scripts/capture.sh

ENV FEATURE_NAME=screen
ENV UPDATE_GOLDENS=1

ENTRYPOINT ["/scripts/capture.sh"]
