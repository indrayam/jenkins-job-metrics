from __future__ import print_function
import datetime
import time
import math
import shlex
import sys
import os
import glob
from subprocess import Popen, PIPE
import xml.etree.ElementTree as ET
from color import red, green, yellow, blue, magenta, cyan, white


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


def process_build_xml_file_list(run_date, all_runs_file, jobs_output_data_folder):

    # define variables to capture overall data
    total_num_of_jobs = 0
    job_runs = {}
    job_runs_by_org = {}
    job_results = {}
    nodes = {}
    total_num_of_jobs_by_hr = {
                    '00': 0, '01': 0, '02': 0, '03': 0, '04': 0, '05': 0, '06': 0, '07': 0, '08': 0, '09': 0, '10': 0, '11': 0, '12': 0,
                    '13': 0, '14': 0, '15': 0, '16': 0, '17': 0, '18': 0, '19': 0, '20': 0, '21': 0, '22': 0, '23': 0
                    }
    

    # Process all build.xml files in all-runs.txt and set up dictionary of dictionaries data structure
    ts = time.time()
    audit_timestamp = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d_%H-%M-%S')
    audit_log_file = open(jobs_output_data_folder + '/audit/' + run_date + '_' + audit_timestamp + '-audit.log', 'w')
    with open(all_runs_file, 'r') as file:
        for line in file:
            build_xml_file_name = line.strip()
            job_key, job_name, job_date, job_time_hr, job_time_min, job_run_basics_status = get_job_run_basics(build_xml_file_name)
            if job_run_basics_status == '_ERR_':
                audit_log_file.write('_ERR_: File Path Parsing Error ' + build_xml_file_name + '\n')
                continue
            job_duration, job_builton, job_result, process_build_status = process_build_xml_file(build_xml_file_name)
            if process_build_status == '_ERR_':
                audit_log_file.write('_ERR_: File Does not Exist Error ' + build_xml_file_name + '\n')
                continue
            audit_log_file.write(job_key + '|' + job_date + '|' + job_time_hr + ':' + job_time_min + '|' + job_duration + '|' + job_builton + '|' + job_result + '\n')
            
            # Create a total count of all the jobs
            total_num_of_jobs = total_num_of_jobs + 1
            
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
                'duration': []
                }
            nodes[job_builton]['time'][job_time_hr] = nodes[job_builton]['time'][job_time_hr] + 1
            nodes[job_builton]['status'][job_result] = nodes[job_builton]['status'][job_result] + 1
            if job_result == 'SUCCESS': 
                nodes[job_builton]['duration'].append(int(job_duration))
            
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
    jobs_summary_report_filename = jobs_output_data_folder + run_date + '.txt'
    generate_ci_metrics_report(run_date, total_num_of_jobs, nodes, jobs_summary_report_filename, job_runs, job_results, job_runs_by_org, total_num_of_jobs_by_hr)


def generate_ci_metrics_report(run_date, total_num_of_jobs, nodes, jobs_summary_report_filename, job_runs, job_results, job_runs_by_org, total_num_of_jobs_by_hr):
    run_date_obj = datetime.datetime.strptime(run_date, '%Y-%m-%d').date()
    summary = open(jobs_summary_report_filename, 'w')

    ci_metrics_report = '*' * 150 + "\n"

    fragment1 = "Date of CI Metrics Report Run: " + yellow(run_date) + "\n"
    ci_metrics_report = ci_metrics_report + fragment1

    fragment2 = "Day of the week: " + run_date_obj.strftime("%A") + "\n"
    ci_metrics_report = ci_metrics_report + fragment2

    fragment3 = "Total Number of Job Runs: " + green(total_num_of_jobs) + "\n"
    ci_metrics_report = ci_metrics_report + fragment3
    
    fragment4 = "\tJob Run Count By Build Status: "
    ci_metrics_report = ci_metrics_report + fragment4
    job_result_output = ''
    for job_result_type, job_result_frequency in job_results.items():
        if job_result_type == 'SUCCESS':
            job_result_output = job_result_output + job_result_type + ' = ' + green(job_result_frequency) + ', '
        else:
            job_result_output = job_result_output + job_result_type + ' = ' + red(job_result_frequency) + ', '
    job_result_output = job_result_output.strip(', ') + "\n"
    ci_metrics_report = ci_metrics_report + job_result_output

    fragment5 = "\tJob Run Timeline (PST): |"
    ci_metrics_report = ci_metrics_report + fragment5
    overall_job_run_timeline_output = ''
    for hr in sorted(total_num_of_jobs_by_hr.keys()):
        if total_num_of_jobs_by_hr[hr] != 0:
            overall_job_run_timeline_output = overall_job_run_timeline_output + red(str(total_num_of_jobs_by_hr[hr])) + '|'
        else:
            overall_job_run_timeline_output = overall_job_run_timeline_output + str(total_num_of_jobs_by_hr[hr]) + '|'
    ci_metrics_report = ci_metrics_report + overall_job_run_timeline_output + "\n"

    fragment6 = "Total Number of Unique Jobs: " + green(len(job_runs)) + "\n"
    ci_metrics_report = ci_metrics_report + fragment6
 
    fragment7 = "Top 5 Orgs, by Job Runs:" + "\n"
    ci_metrics_report = ci_metrics_report + fragment7
    job_org_count = 0
    top5_orgs_output = ''
    for job_org, job_org_run in sorted(job_runs_by_org.iteritems(), key=lambda (k,v): (v, k), reverse=True):
        job_org_count = job_org_count + 1
        job_org
        if job_org_count < 6:
            if job_org_count == 1:
                top5_orgs_output = top5_orgs_output + "\t" + job_org + " = " + green(job_org_run) + "\n"
            else:
                top5_orgs_output = top5_orgs_output + "\t" + job_org + " = " + str(job_org_run) + "\n"
    ci_metrics_report = ci_metrics_report + top5_orgs_output

    fragment8 = "Top 5 Jobs, by Job Runs:" + "\n"
    ci_metrics_report = ci_metrics_report + fragment8
    top5_jobs_output = ''
    job_count = 0
    for job, job_run in sorted(job_runs.iteritems(), key=lambda (k,v): (v, k), reverse=True):
        job_count = job_count + 1
        if job_count < 6:
            if job_count == 1:
                top5_jobs_output = top5_jobs_output + "\t" + job + " = " + green(job_run) + "\n"
            else:
                top5_jobs_output = top5_jobs_output + "\t" + job + " = " + str(job_run) + "\n"
    ci_metrics_report = ci_metrics_report + top5_jobs_output

    fragment9 = "Job Run Details, By Nodes:" + "\n"
    ci_metrics_report = ci_metrics_report + fragment9
    for node, node_stats_type in nodes.items():
        node_total_count = 0

        node_times_values = node_stats_type['time'].values()
        node_max_count = max(node_times_values)
        node_min_count = min(node_times_values)
        node_count_p50, node_count_p75 = return_percentiles(node_times_values)
        node_hourly_output = '\t\tJob Run Timeline (PST): |'
        for hr in sorted(node_stats_type['time'].keys()):
            node_total_count = node_total_count + node_stats_type['time'][hr]
            if node_stats_type['time'][hr] != 0 and node_stats_type['time'][hr] > 12:
                node_hourly_output = node_hourly_output + red(str(node_stats_type['time'][hr])) + '|'
            else:
                node_hourly_output = node_hourly_output + str(node_stats_type['time'][hr]) + '|'
        node_hourly_output = node_hourly_output + "\n"

        # Job Run Count Output By Node
        fragment10 = "\tTotal Job Runs on Node \"" +  node + "\" = " + green(node_total_count) + "\n"
        ci_metrics_report = ci_metrics_report + fragment10
        node_count_stats_output = "\t\tJob Run Count Stats: Max Job Runs per Hr = " + magenta(node_max_count) + ", Min Job Runs per Hr = " + magenta(node_min_count) + ", 50th-percentile = " + magenta(node_count_p50) + ", 75th-percentile = " + magenta(node_count_p75) + "\n"
        ci_metrics_report = ci_metrics_report + node_count_stats_output
        
        # Build Status Count Output By Node
        node_status_output = '\t\tJob Run Count By Build Status: '
        for st in node_stats_type['status'].keys():
            node_status_output = node_status_output + st + ' = ' + blue(node_stats_type['status'][st]) + ', '
        node_status_output = node_status_output.strip(', ') + "\n"
        ci_metrics_report = ci_metrics_report + node_status_output

        # Duration Stats Output By Node
        node_duration_values = node_stats_type['duration']
        if len(node_duration_values) > 0:
            node_max_duration = user_friendly_secs(max(node_duration_values))
            node_min_duration = user_friendly_secs(min(node_duration_values))
            node_duration_p50, node_duration_p75 = return_percentiles(node_duration_values)
            node_duration_p50 = user_friendly_secs(node_duration_p50)
            node_duration_p75 = user_friendly_secs(node_duration_p75)
        else:
            node_max_duration = 'NA'
            node_min_duration = 'NA'
            node_duration_p50 = 'NA'
            node_duration_p75 = 'NA'
        node_duration_output = '\t\tJob Run Duration Stats (in mins): Max Duration = ' + cyan(node_max_duration) + ', Min Duration = ' + cyan(node_min_duration) + ', 50th-percentile = ' + cyan(node_duration_p50) + ", 75th-percentile =" + cyan(node_duration_p75) + "\n"
        ci_metrics_report = ci_metrics_report + node_duration_output
        
        # Timeline Output By Node
        ci_metrics_report = ci_metrics_report + node_hourly_output


    ci_metrics_report = ci_metrics_report + '*' * 150 + "\n"
    print(ci_metrics_report,end='')
    summary.write(ci_metrics_report)
    summary.close()


def user_friendly_secs(ms):
    seconds = ms / 1000.0
    minutes = seconds / 60.0
    return '%.2f' % minutes


def return_percentiles(list_of_numbers):
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
    job_duration, job_builton, job_result, process_build_status = "Undef", "Undef", "Undef", "_ERR_"
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
    return job_duration, job_builton, job_result, process_build_status


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


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print('Usage: %s <top-level-jobs-folder> <date-in-the-format: (YYYY-MM-DD)>' % sys.argv[0])
        sys.exit(1)
    else:
        run_date = sys.argv[2]
        jobs_output_data_folder = os.getcwd() + '/ci-metrics-python/'
        jobs_output_data_folder_audit = jobs_output_data_folder + '/audit/'
        if not os.path.exists(jobs_output_data_folder_audit):
            os.makedirs(jobs_output_data_folder_audit)
        top_level_folder_path = sys.argv[1]
        run_date = sys.argv[2]
        all_runs_file = os.getcwd() + '/all-runs.txt'
        generate_build_xml_file_list(top_level_folder_path, all_runs_file, run_date)
        process_build_xml_file_list(run_date, all_runs_file, jobs_output_data_folder)
