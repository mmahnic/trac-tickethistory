#!/usr/bin/env bash

# Must be run in an environment created by ./setupLocalEnv.sh

cd ../..
python -B -m tickethistory.test.workdays_t
python -B -m tickethistory.test.distributor_t
