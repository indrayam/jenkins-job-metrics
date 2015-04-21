#!/bin/bash
timestamp() {
   date +"%Y-%m-%d_%H-%M-%S"
}

cron_log_file="/tmp/cron-daily-ci-summary-report-$(timestamp).txt"
ci_daily_report_home="/apps/dftjenkins/workspace/ci-daily-reports"
echo "Changing directory to $ci_daily_report_home..."
cd $ci_daily_report_home
source /apps/dftjenkins/workspace/bootstrap/bin/activate
python ci-summary-report.py -f /apps/dftjenkins/JENKINS_HOME/jobs -sd 'yesterday' -ct 'daily' -p 'Snz1ylE0pxf!' >  $cron_log_file 2>&1

