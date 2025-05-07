#!/bin/bash

if [ "$1" == "api-ninja" ]; then
    shift # Remove the first argument
    .venv/bin/api-ninja "$@"
elif [ "$1" == "pytest" ]; then
    shift # Remove the first argument
    .venv/bin/pytest "$@"
else
    echo "Usage: $0 {api-ninja|pytest} [arguments]"
    exit 1
fi