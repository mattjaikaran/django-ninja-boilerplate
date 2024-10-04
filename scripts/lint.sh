#!/bin/bash

# lint.sh

source env/bin/activate
flake8 .
black .
isort .