from __future__ import print_function
import datetime
import time
import math
import shlex
import sys
import os
import glob
import smtplib
from subprocess import Popen, PIPE
import xml.etree.ElementTree as ET
from color import red, green, yellow, blue, magenta, cyan, white


def generate_config_xml_file_list(top_level_folder_path, all_jobs_file, run_date):
    cmd = 'ag -l --depth 50 --xml \"<project>|</maven2-moduleset>\" ' + top_level_folder_path
    args = shlex.split(cmd)
    with open(all_jobs_file, 'w') as out:
        p2 = Popen(args, stdout=out, stderr=PIPE, stdin=PIPE, cwd=os.getcwd())
        output, err = p2.communicate()
        rc = p2.returncode
        if rc > 0:
            print(err.decode('utf-8'), end='')


def process_config_xml_file_list(run_date, run_timestamp, all_jobs_file, jobs_output_data_folder):
    jobs = {}

    # Process all config.xml files in all-jobs.txt and set up dictionary of dictionaries data structure
    audit_job_log_file = open(jobs_output_data_folder + '/audit/' + run_date + '_' + run_timestamp + '-audit-jobs.log', 'w')
    with open(all_jobs_file, 'r') as file:
        for line in file:
            config_xml_file_name = line.strip()
            job_key, job_name, job_basics_status = get_job_basics(config_xml_file_name)
            if job_basics_status == '_ERR_':
                audit_job_log_file.write('_ERR_: File Path Parsing Error ' + build_xml_file_name + '\n')
                continue
            audit_job_log_file.write(job_key + '|' + job_name + '\n')
            # print('job_key', job_key, 'job_name', job_name)
            
            # Jobs Dictionary of Dictionary
            if job_key not in jobs:
                jobs[job_key] = { 'name': job_name}

    return jobs 


def get_job_basics(job_run):
    job_key, job_name, job_basics_status = "Undef", "Undef", "_ERR_"
    line_tokens = job_run.split('/')
    job_key = get_job_key(line_tokens[:-1])
    job_name = line_tokens[-2]
    if job_name != "Undef":
        job_basics_status = "SUCCESS"
    return job_key, job_name, job_basics_status


def generate_build_xml_file_list(top_level_folder_path, all_runs_file, run_date):
    cmd = 'find ' + top_level_folder_path + ' -name build.xml'
    args = shlex.split(cmd)
    p1 = Popen(args,
              stdout=PIPE, stderr=PIPE, cwd=os.getcwd())
    cmd = 'grep ' + run_date
    args = shlex.split(cmd)
    with open(all_runs_file, 'w') as out:
        p2 = Popen(args, stdout=out, stderr=PIPE, stdin=p1.stdout, cwd=os.getcwd())
        output, err = p2.communicate()
        rc = p2.returncode
        if rc > 0:
            print(err.decode('utf-8'), end='')


def process_build_xml_file_list(run_date, run_timestamp, all_runs_file, jobs_output_data_folder, all_jobs):

    # define variables to capture overall data
    total_num_of_job_runs = 0
    job_runs = {}
    job_runs_by_org = {}
    job_results = {}
    nodes = {}
    total_num_of_jobs_by_hr = {
                    '00': 0, '01': 0, '02': 0, '03': 0, '04': 0, '05': 0, '06': 0, '07': 0, '08': 0, '09': 0, '10': 0, '11': 0, '12': 0,
                    '13': 0, '14': 0, '15': 0, '16': 0, '17': 0, '18': 0, '19': 0, '20': 0, '21': 0, '22': 0, '23': 0
                    }
    

    # Process all build.xml files in all-runs.txt and set up dictionary of dictionaries data structure
    audit_log_file = open(jobs_output_data_folder + '/audit/' + run_date + '_' + run_timestamp + '-audit.log', 'w')
    with open(all_runs_file, 'r') as file:
        for line in file:
            build_xml_file_name = line.strip()
            job_key, job_name, job_date, job_time_hr, job_time_min, job_run_basics_status = get_job_run_basics(build_xml_file_name)
            if job_run_basics_status == '_ERR_':
                audit_log_file.write('_ERR_: File Path Parsing Error ' + build_xml_file_name + '\n')
                continue
            job_number, job_duration, job_builton, job_result, process_build_status = process_build_xml_file(build_xml_file_name)
            if process_build_status == '_ERR_':
                audit_log_file.write('_ERR_: File Does not Exist Error ' + build_xml_file_name + '\n')
                continue
            job_url = get_job_url(job_key, job_number)
            audit_log_file.write(job_key + '|' + job_number + '|' + job_date + '|' + job_time_hr + ':' + job_time_min + '|' + job_duration + '|' + job_builton + '|' + job_result + '|' + job_url + '\n')
            
            # Create a total count of all the jobs
            total_num_of_job_runs = total_num_of_job_runs + 1
            
            # Nodes Dictionary of Dictionaries
            if job_builton not in nodes:
                nodes[job_builton] = { 
                'time': {
                    '00': 0, '01': 0, '02': 0, '03': 0, '04': 0, '05': 0, '06': 0, '07': 0, '08': 0, '09': 0, '10': 0, '11': 0, '12': 0,
                    '13': 0, '14': 0, '15': 0, '16': 0, '17': 0, '18': 0, '19': 0, '20': 0, '21': 0, '22': 0, '23': 0
                    }, 
                'status': {
                    'Undef': 0, 'SUCCESS': 0, 'NOT_BUILT': 0, 'FAILURE': 0, 'UNSTABLE': 0, 'ABORTED': 0
                    }, 
                'duration': {}
                }
            nodes[job_builton]['time'][job_time_hr] = nodes[job_builton]['time'][job_time_hr] + 1
            nodes[job_builton]['status'][job_result] = nodes[job_builton]['status'][job_result] + 1
            if job_result == 'SUCCESS': 
                nodes[job_builton]['duration'][job_url] = int(job_duration)
            
            # Job Runs Count Dictionary
            if job_key not in job_runs:
                job_runs[job_key] = 1
            else:
                job_runs[job_key] = job_runs[job_key] + 1
            
            # Job Result Dictionary
            if job_result not in job_results:
                job_results[job_result] = 1
            else:
                job_results[job_result] = job_results[job_result] + 1

            # Job Organization Dictionary
            job_org_key = job_key.split(':')[0]
            if job_org_key not in job_runs_by_org:
                job_runs_by_org[job_org_key] = 1
            else:
                job_runs_by_org[job_org_key] = job_runs_by_org[job_org_key] + 1

            # Total Number of Jobs by Hr
            total_num_of_jobs_by_hr[job_time_hr] = total_num_of_jobs_by_hr[job_time_hr] + 1
    
    # Close the Audit log file
    audit_log_file.close()

    # Generate summary report
    generate_ci_metrics_report(run_date, run_timestamp, all_jobs, total_num_of_job_runs, nodes, job_runs, job_results, job_runs_by_org, total_num_of_jobs_by_hr)


def generate_ci_metrics_report(run_date, run_timestamp, all_jobs, total_num_of_job_runs, nodes, job_runs, job_results, job_runs_by_org, total_num_of_jobs_by_hr):
    run_date_obj = datetime.datetime.strptime(run_date, '%Y-%m-%d').date()
    jobs_summary_report_filename = get_summary_report_filename(jobs_output_data_folder, run_date, run_timestamp)
    summary = open(jobs_summary_report_filename, 'w')

    ci_metrics_report = '*' * 150 + "\n"
    ci_metrics_report_plain = ci_metrics_report

    fragment1 = "Date of CI Metrics Report Run: " + yellow(run_date) + "\n"
    pfragment1 = "Date of CI Metrics Report Run: " + str(run_date) + "\n"
    ci_metrics_report = ci_metrics_report + fragment1
    ci_metrics_report_plain = ci_metrics_report_plain + pfragment1

    fragment2 = "Day of the week: " + run_date_obj.strftime("%A") + "\n"
    ci_metrics_report = ci_metrics_report + fragment2
    ci_metrics_report_plain = ci_metrics_report_plain + fragment2

    total_num_of_jobs = 0
    for job_key, job_details in all_jobs.items():
        total_num_of_jobs = total_num_of_jobs + 1

    today = datetime.date.today()
    stoday = today.strftime('%Y-%m-%d')
    fragment3a = "Total Number of Unique Jobs in CI: " + green(total_num_of_jobs) + " (as of " + stoday + ")\n"
    pfragment3a = "Total Number of Unique Jobs in CI: " + str(total_num_of_jobs) + " (as of " + stoday + ")\n"
    ci_metrics_report = ci_metrics_report + fragment3a
    ci_metrics_report_plain = ci_metrics_report_plain + pfragment3a

    fragment3b = "Total Number of Job Runs: " + green(total_num_of_job_runs) + "\n"
    pfragment3b = "Total Number of Job Runs: " + str(total_num_of_job_runs) + "\n"
    ci_metrics_report = ci_metrics_report + fragment3b
    ci_metrics_report_plain = ci_metrics_report_plain + pfragment3b
    
    fragment4 = "\tJob Run Count By Build Status: "
    ci_metrics_report = ci_metrics_report + fragment4
    ci_metrics_report_plain = ci_metrics_report_plain + fragment4
    job_result_output = ''
    pjob_result_output = ''
    for job_result_type, job_result_frequency in job_results.items():
        if job_result_type == 'SUCCESS':
            job_result_output = job_result_output + job_result_type + ' = ' + green(job_result_frequency) + ', '
        else:
            job_result_output = job_result_output + job_result_type + ' = ' + red(job_result_frequency) + ', '
        pjob_result_output = pjob_result_output + job_result_type + ' = ' + str(job_result_frequency) + ', '
    job_result_output = job_result_output.strip(', ') + "\n"
    pjob_result_output = pjob_result_output.strip(', ') + "\n"
    ci_metrics_report = ci_metrics_report + job_result_output
    ci_metrics_report_plain = ci_metrics_report_plain + pjob_result_output

    fragment5 = "\tJob Run Timeline (PST): |"
    ci_metrics_report = ci_metrics_report + fragment5
    ci_metrics_report_plain = ci_metrics_report_plain + fragment5
    overall_job_run_timeline_output = ''
    poverall_job_run_timeline_output = ''
    for hr in sorted(total_num_of_jobs_by_hr.keys()):
        if total_num_of_jobs_by_hr[hr] != 0:
            overall_job_run_timeline_output = overall_job_run_timeline_output + red(str(total_num_of_jobs_by_hr[hr])) + '|'
        else:
            overall_job_run_timeline_output = overall_job_run_timeline_output + str(total_num_of_jobs_by_hr[hr]) + '|'
        poverall_job_run_timeline_output = poverall_job_run_timeline_output + str(total_num_of_jobs_by_hr[hr]) + '|'
    ci_metrics_report = ci_metrics_report + overall_job_run_timeline_output + "\n"
    ci_metrics_report_plain = ci_metrics_report_plain + poverall_job_run_timeline_output + "\n"

    fragment6 = "\tJobs That Ran: " + green(len(job_runs)) + "\n"
    pfragment6 = "\tJobs That Ran: " + str(len(job_runs)) + "\n"
    ci_metrics_report = ci_metrics_report + fragment6
    ci_metrics_report_plain = ci_metrics_report_plain + pfragment6
 
    fragment7 = "Top 5 Orgs, by Job Runs:" + "\n"
    ci_metrics_report = ci_metrics_report + fragment7
    ci_metrics_report_plain = ci_metrics_report_plain + fragment7
    job_org_count = 0
    top5_orgs_output = ''
    ptop5_orgs_output = ''
    for job_org, job_org_run in sorted(job_runs_by_org.iteritems(), key=lambda (k,v): (v, k), reverse=True):
        job_org_count = job_org_count + 1
        if job_org_count < 6:
            if job_org_count == 1:
                top5_orgs_output = top5_orgs_output + "\t" + job_org + " = " + green(job_org_run) + "\n"
            else:
                top5_orgs_output = top5_orgs_output + "\t" + job_org + " = " + str(job_org_run) + "\n"
            ptop5_orgs_output = ptop5_orgs_output + "\t" + job_org + " = " + str(job_org_run) + "\n"
    ci_metrics_report = ci_metrics_report + top5_orgs_output
    ci_metrics_report_plain = ci_metrics_report_plain + ptop5_orgs_output

    fragment8 = "Top 5 Jobs, by Job Runs:" + "\n"
    ci_metrics_report = ci_metrics_report + fragment8
    ci_metrics_report_plain = ci_metrics_report_plain + fragment8
    top5_jobs_output = ''
    ptop5_jobs_output = ''
    job_count = 0
    for job, job_run in sorted(job_runs.iteritems(), key=lambda (k,v): (v, k), reverse=True):
        job_count = job_count + 1
        if job_count < 6:
            if job_count == 1:
                top5_jobs_output = top5_jobs_output + "\t" + job + " = " + green(job_run) + "\n"
            else:
                top5_jobs_output = top5_jobs_output + "\t" + job + " = " + str(job_run) + "\n"
            ptop5_jobs_output = ptop5_jobs_output + "\t" + job + " = " + str(job_run) + "\n"
    ci_metrics_report = ci_metrics_report + top5_jobs_output
    ci_metrics_report_plain = ci_metrics_report_plain + ptop5_jobs_output

    fragment9 = "Job Run Details, By Nodes:" + "\n"
    ci_metrics_report = ci_metrics_report + fragment9
    ci_metrics_report_plain = ci_metrics_report_plain + fragment9
    for node, node_stats_type in nodes.items():
        node_total_count = 0

        node_times_values = node_stats_type['time'].values()
        node_max_count = max(node_times_values)
        node_min_count = min(node_times_values)
        node_count_p50, node_count_p75 = get_percentiles(node_times_values)
        node_hourly_output = '\t\tJob Run Timeline (PST): |'
        pnode_hourly_output = '\t\tJob Run Timeline (PST): |'
        for hr in sorted(node_stats_type['time'].keys()):
            node_total_count = node_total_count + node_stats_type['time'][hr]
            if node_stats_type['time'][hr] != 0 and node_stats_type['time'][hr] > 12:
                node_hourly_output = node_hourly_output + red(str(node_stats_type['time'][hr])) + '|'
            else:
                node_hourly_output = node_hourly_output + str(node_stats_type['time'][hr]) + '|'
            pnode_hourly_output = pnode_hourly_output + str(node_stats_type['time'][hr]) + '|'
        node_hourly_output = node_hourly_output + "\n"
        pnode_hourly_output = pnode_hourly_output + "\n"

        # Job Run Count Output By Node
        fragment10 = "\tTotal Job Runs on Node \"" +  node + "\" = " + green(node_total_count) + "\n"
        pfragment10 = "\tTotal Job Runs on Node \"" +  node + "\" = " + str(node_total_count) + "\n"
        ci_metrics_report = ci_metrics_report + fragment10
        ci_metrics_report_plain = ci_metrics_report_plain + pfragment10
        node_count_stats_output = "\t\tJob Run Count Stats: Max Job Runs per Hr = " + magenta(node_max_count) + ", Min Job Runs per Hr = " + magenta(node_min_count) + ", 50th-percentile = " + magenta(node_count_p50) + ", 75th-percentile = " + magenta(node_count_p75) + "\n"
        pnode_count_stats_output = "\t\tJob Run Count Stats: Max Job Runs per Hr = " + str(node_max_count) + ", Min Job Runs per Hr = " + str(node_min_count) + ", 50th-percentile = " + str(node_count_p50) + ", 75th-percentile = " + str(node_count_p75) + "\n"
        ci_metrics_report = ci_metrics_report + node_count_stats_output
        ci_metrics_report_plain = ci_metrics_report_plain + pnode_count_stats_output
        
        # Build Status Count Output By Node
        node_status_output = '\t\tJob Run Count By Build Status: '
        pnode_status_output = '\t\tJob Run Count By Build Status: '
        for st in node_stats_type['status'].keys():
            node_status_output = node_status_output + st + ' = ' + blue(node_stats_type['status'][st]) + ', '
            pnode_status_output = pnode_status_output + st + ' = ' + str(node_stats_type['status'][st]) + ', '
        node_status_output = node_status_output.strip(', ') + "\n"
        pnode_status_output = pnode_status_output.strip(', ') + "\n"
        ci_metrics_report = ci_metrics_report + node_status_output
        ci_metrics_report_plain = ci_metrics_report_plain + pnode_status_output

        # Duration Stats Output By Node
        node_duration_values = list(node_stats_type['duration'].values())
        if len(node_duration_values) > 0:
            node_max_duration_msec = max(node_duration_values)
            node_max_duration = user_friendly_secs(node_max_duration_msec)
            node_max_duration_url = get_job_url_by_duration(node_stats_type['duration'], node_max_duration_msec)
            node_min_duration = user_friendly_secs(min(node_duration_values))
            node_duration_p50, node_duration_p75 = get_percentiles(node_duration_values)
            node_duration_p50 = user_friendly_secs(node_duration_p50)
            node_duration_p75 = user_friendly_secs(node_duration_p75)
        else:
            node_max_duration = 'NA'
            node_max_duration_url = 'NA'
            node_min_duration = 'NA'
            node_duration_p50 = 'NA'
            node_duration_p75 = 'NA'
        node_duration_output = '\t\tJob Run Duration Stats (in mins): Max Duration = ' + cyan(node_max_duration) + ', Min Duration = ' + cyan(node_min_duration) + ', 50th-percentile = ' + cyan(node_duration_p50) + ', 75th-percentile = ' + cyan(node_duration_p75) + '\n'
        node_duration_output = node_duration_output + '\t\tConsole Output URL of Job with Max Duration (' + node_max_duration + ' mins): ' + node_max_duration_url + '/console' + '\n'
        pnode_duration_output = '\t\tJob Run Duration Stats (in mins): Max Duration = ' + str(node_max_duration) + ', Min Duration = ' + str(node_min_duration) + ', 50th-percentile = ' + str(node_duration_p50) + ', 75th-percentile = ' + str(node_duration_p75) + '\n'
        pnode_duration_output = pnode_duration_output + '\t\tConsole Output URL of Job with Max Duration (' + node_max_duration + ' mins:) ' + node_max_duration_url + '/console' + '\n'
        ci_metrics_report = ci_metrics_report + node_duration_output
        ci_metrics_report_plain = ci_metrics_report_plain + pnode_duration_output
        
        # Timeline Output By Node
        ci_metrics_report = ci_metrics_report + node_hourly_output
        ci_metrics_report_plain = ci_metrics_report_plain + pnode_hourly_output


    ci_metrics_report = ci_metrics_report + '*' * 150 + "\n"
    ci_metrics_report_plain = ci_metrics_report_plain + '*' * 150 + "\n"
    print(ci_metrics_report,end='')
    summary.write(ci_metrics_report)
    summary.close()

    # Send the CI Metrics Report as Email
    send_ci_report_in_email(run_date, ci_metrics_report_plain)


def send_ci_report_in_email(run_date, ci_metrics_report):
    email_user = "anasharm@cisco.com"
    # email_pwd = ""
    FROM = "anasharm@cisco.com"
    TO = ["anasharm@cisco.com", "sujmuthu@cisco.com", "vivekse@cisco.com", "plashkar@cisco.com", "dhsanghv@cisco.com", "azsivara@cisco.com", "vijmanda@cisco.com", "dchrist2@cisco.com", "avijayku@cisco.com", "yogyadav@cisco.com", "mehaggar@cisco.com", "rbaratam@cisco.com", "jvenanci@cisco.com"]
    SUBJECT = "CI Job Run Summary Report for " + run_date
    TEXT = ci_metrics_report

    # Prepare actual message
    message = """\From: %s\nTo: %s\nSubject: %s\n\n%s
    """ % (FROM, ", ".join(TO), SUBJECT, TEXT)
    try:
        server = smtplib.SMTP("email.cisco.com", 587) 
        server.ehlo()
        server.starttls()
        server.login(email_user, email_pwd)
        server.sendmail(FROM, TO, message)
        server.close()
        print("Successfully sent email with Subject:", SUBJECT)
    except:
        print("WARNING: Failed to send email with Subject:", SUBJECT)


def get_summary_report_filename(jobs_output_data_folder, run_date, run_timestamp):
    jobs_summary_report_filename = jobs_output_data_folder + run_date + '.txt'
    if os.path.isfile(jobs_summary_report_filename):
        jobs_summary_report_filename = jobs_output_data_folder + run_date + '_' + run_timestamp + '.txt'
    return jobs_summary_report_filename


def user_friendly_secs(ms):
    seconds = ms / 1000.0
    minutes = seconds / 60.0
    return '%.2f' % minutes


def get_percentiles(list_of_numbers):
    list_of_numbers_sorted = sorted(list_of_numbers)
    p50 = percentile(list_of_numbers_sorted, 0.50)
    p75 = percentile(list_of_numbers_sorted, 0.75)
    return p50, p75


def percentile(N, percent, key=lambda x:x):
    """
    Find the percentile of a list of values.

    @parameter N - is a list of values. Note N MUST BE already sorted.
    @parameter percent - a float value from 0.0 to 1.0.
    @parameter key - optional key function to compute value from each element of N.

    @return - the percentile of the values
    """
    if not N:
        return None
    k = (len(N)-1) * percent
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return key(N[int(k)])
    d0 = key(N[int(f)]) * (c-k)
    d1 = key(N[int(c)]) * (k-f)
    return d0+d1


def process_build_xml_file(build_xml_file_name):
    job_number, job_duration, job_builton, job_result, process_build_status = "Undef", "Undef", "Undef", "Undef", "_ERR_"
    if os.path.isfile(build_xml_file_name):
        process_build_status = "SUCCESS"
        tree = ET.parse(build_xml_file_name)
        root = tree.getroot()
        for child in root:
            if child.tag == 'duration':
                job_duration = child.text
            elif child.tag == 'builtOn':
                job_builton = child.text
            elif child.tag == 'result':
                job_result = child.text
            elif child.tag == 'number':
                job_number = child.text
    return job_number, job_duration, job_builton, job_result, process_build_status


def get_job_run_basics(job_run):
    job_key, job_name, job_date, job_time_hr, job_time_min, job_run_basics_status = "Undef", "Undef", "Undef", "Undef", "Undef", "_ERR_"
    line_tokens = job_run.split('/')
    if line_tokens[-3] == 'builds':
        job_run_basics_status = "SUCCESS"
        job_key = get_job_key(line_tokens[:-3])
        job_name = line_tokens[-4]
        job_date_tokens = line_tokens[-2].split('_')
        job_date = job_date_tokens[0]
        job_time_tokens = job_date_tokens[1].split('-')
        job_time_hr = job_time_tokens[0]
        job_time_min = job_time_tokens[1]
    return job_key, job_name, job_date, job_time_hr, job_time_min, job_run_basics_status


def get_job_key(line_tokens):
    count = 0
    for el in line_tokens:
        if el == 'jobs' and count == 0:
            job_key = ''
            count = count + 1
        elif el != 'jobs':
            if count == 1:
                job_key = el
                count = count + 1
            else:
                job_key = job_key + ':' + el

    return job_key


def get_job_url(job_key, job_number):
    job_key_elements = job_key.split(':')
    job_url = 'https://ci.cisco.com'
    index = 0
    index_for_modules = -2
    for el in job_key_elements:
        if el == 'modules':
            index_for_modules = index
            index = index + 1
            continue
        if index == index_for_modules + 1:
            job_url = job_url + '/' + el
        else:
            job_url = job_url + '/job/' + el
        index = index + 1
    job_url = job_url + '/' + job_number
    return job_url


def get_job_url_by_duration(node_duration_dict, node_max_duration_msec):
    job_url = 'Undef'
    for url, duration in node_duration_dict.items():
        if duration == node_max_duration_msec:
            job_url = url
            break
    return job_url    



def print_usage_and_exit():
    usage = 'Usage: list-all-job-runs.py <top-level-jobs-folder> <start-date: (YYYY-MM-DD)> <end-date: (YYYY-MM-DD) | OPTIONAL>'
    print(usage)
    sys.exit(1)


if __name__ == "__main__":
    
    if len(sys.argv) < 2:
        print_usage_and_exit()
    else:
        # Create the folder for storing CI Metrics and Job Audit Log files
        jobs_output_data_folder = os.getcwd() + '/ci-metrics-python/'
        jobs_output_data_folder_audit = jobs_output_data_folder + '/audit/'
        if not os.path.exists(jobs_output_data_folder_audit):
            os.makedirs(jobs_output_data_folder_audit)
        top_level_folder_path = sys.argv[1]
        
        # Grab or Derive the Start Date
        if len(sys.argv) > 2:
            start_date = sys.argv[2]
        else:
            yesterday = datetime.date.today() - datetime.timedelta(1)
            start_date = yesterday.strftime('%Y-%m-%d')
        start_date_obj = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()

        # Grab or Derive the End Date
        if len(sys.argv) > 3:
                end_date = sys.argv[3]
        else:
            end_date = start_date
        end_date_obj = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()

        # Make sure the End Date is same or ahead of Start Date 
        if end_date_obj >= start_date_obj:
            delta = end_date_obj - start_date_obj
            for d in range(delta.days + 1):
                run_date_obj = start_date_obj + datetime.timedelta(days=d)
                run_date = run_date_obj.strftime('%Y-%m-%d')
                all_runs_file = os.getcwd() + '/all-runs.txt'
                all_jobs_file = os.getcwd() + '/all-jobs.txt'
                
                # Get a timestamp for all the logs
                ts = time.time()
                run_timestamp = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d_%H-%M-%S')

                # Get Jobs Metrics
                generate_config_xml_file_list(top_level_folder_path, all_jobs_file, run_date)
                all_jobs = process_config_xml_file_list(run_date, run_timestamp, all_jobs_file, jobs_output_data_folder)

                # Get Job Runs Metrics
                generate_build_xml_file_list(top_level_folder_path, all_runs_file, run_date)
                process_build_xml_file_list(run_date, run_timestamp, all_runs_file, jobs_output_data_folder, all_jobs)
        else:
            print_usage_and_exit()
