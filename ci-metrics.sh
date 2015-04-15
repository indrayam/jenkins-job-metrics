#!/bin/bash

timestamp() {
   date +"%Y-%m-%d_%H-%M-%S"
}

cron_log_file="/tmp/list-all-job-runs-$(timestamp).txt"
ci_daily_report_home="/apps/dftjenkins/workspace/ci-daily-reports"
echo "Changing directory to $ci_daily_report_home..."
cd $ci_daily_report_home
source /apps/dftjenkins/workspace/bootstrap/bin/activate
python list-all-job-runs.py /apps/dftjenkins/JENKINS_HOME/jobs > $cron_log_file 2>&1 
