from __future__ import print_function
import datetime
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
    

    # Process all build.xml files in all-runs.txt and set up dictionary of dictionaries data structure
    jobs_output_data_folder_by_date = jobs_output_data_folder + run_date
    with open(all_runs_file, 'r') as file:
        for line in file:
            build_xml_file_name = line.strip()
            job_key, job_name, job_date, job_time_hr, job_time_min = get_job_run_basics(build_xml_file_name)
            job_duration, job_builton, job_result = process_build_xml_file(build_xml_file_name)
            #print(job_key, job_name, job_date, job_time_hr, job_time_min, job_duration, job_builton, job_result)
            total_num_of_jobs = total_num_of_jobs + 1
            if job_builton not in nodes:
                nodes[job_builton] = {
                    '00': 0, '01': 0, '02': 0, '03': 0, '04': 0, '05': 0, '06': 0, '07': 0, '08': 0, '09': 0, '10': 0, '11': 0, '12': 0,
                    '13': 0, '14': 0, '15': 0, '16': 0, '17': 0, '18': 0, '19': 0, '20': 0, '21': 0, '22': 0, '23': 0
                }
            nodes[job_builton][job_time_hr] = nodes[job_builton][job_time_hr] + 1
            
            if job_key not in job_runs:
                job_runs[job_key] = 1
            else:
                job_runs[job_key] = job_runs[job_key] + 1
            
            if job_result not in job_results:
                job_results[job_result] = 1
            else:
                job_results[job_result] = job_results[job_result] + 1

            job_org_key = job_key.split(':')[0]
            if job_org_key not in job_runs_by_org:
                job_runs_by_org[job_org_key] = 1
            else:
                job_runs_by_org[job_org_key] = job_runs_by_org[job_org_key] + 1         
    
    # Generate the node related metrics file for each node that ran a job on that day
    # for node, node_times in nodes.items():
    #     node_file = open(jobs_output_data_folder_by_date + '/' + node + '.txt', 'w')
    #     for hr in sorted(node_times.keys()):
    #         node_file.write(hr + ': ' + str(node_times[hr]) + '\n')
    #     node_file.close()
    
    # Generate summary report
    jobs_summary_report_filename = jobs_output_data_folder + run_date + '.txt'
    generate_ci_metrics_report(run_date, total_num_of_jobs, nodes, jobs_summary_report_filename, job_runs, job_results, job_runs_by_org)


def generate_ci_metrics_report(run_date, total_num_of_jobs, nodes, jobs_summary_report_filename, job_runs, job_results, job_runs_by_org):
    run_date_obj = datetime.datetime.strptime(run_date, '%Y-%m-%d').date()
    summary = open(jobs_summary_report_filename, 'w')
    print('*' * 150)
    summary.write('*' * 150 + '\n')

    print("Date of CI Metrics Report Run:", yellow(run_date))
    summary.write("Date of CI Metrics Report Run: " + yellow(run_date) + '\n')

    print("Day of the week:", run_date_obj.strftime("%A"))
    summary.write("Day of the week: " + run_date_obj.strftime("%A") + '\n')

    print("Total Number of Job Runs:", green(total_num_of_jobs))
    summary.write("Total Number of Job Runs: " + green(total_num_of_jobs) + '\n')
    print("\tJob Run Status: ", end='')
    summary.write("\t")
    job_result_output = ''
    for job_result_type, job_result_frequency in job_results.items():
        if job_result_type == 'SUCCESS':
            job_result_output = job_result_output + job_result_type + ' = ' + green(job_result_frequency) + ', '
        else:
            job_result_output = job_result_output + job_result_type + ' = ' + red(job_result_frequency) + ', '
    job_result_output = job_result_output.strip(', ')
    print(job_result_output)
    summary.write(job_result_output + '\n')

    print("Total Number of Unique Jobs:", green(len(job_runs)))
    summary.write("Total Number of Unique Jobs: " + green(len(job_runs)) + '\n')
 
    job_sub_title = "Top 5 Jobs, by Job Runs:"
    print(job_sub_title)
    summary.write(job_sub_title + '\n')
    job_count = 0
    for job, job_run in sorted(job_runs.iteritems(), key=lambda (k,v): (v, k), reverse=True):
        job_count = job_count + 1
        if job_count < 6:
            print("\t" + job, " = ", job_run)
            summary.write("\t" + job + ' = ' + str(job_run) + '\n')

    job_org_sub_title = "Top 5 Orgs, by Job Runs:"
    print(job_org_sub_title)
    summary.write(job_org_sub_title + '\n')
    job_org_count = 0
    for job_org, job_org_run in sorted(job_runs_by_org.iteritems(), key=lambda (k,v): (v, k), reverse=True):
        job_org_count = job_org_count + 1
        if job_org_count < 6:
            print("\t" + job_org, " = ", job_org_run)
            summary.write("\t" + job_org + ' = ' + str(job_org_run) + '\n')

    nodes_sub_title = "Job Run Details, By Nodes:"
    print(nodes_sub_title)
    summary.write(nodes_sub_title + '\n')
    for node, node_times in nodes.items():
        node_total_count = 0
        node_times_values = node_times.values()
        node_max_count = max(node_times_values)
        node_min_count = min(node_times_values)
        node_duration_p50, node_duration_p75 = return_percentiles(node_times_values)
        node_hourly_output = '\t\tBy Time (PST): |'
        for hr in sorted(node_times.keys()):
            node_total_count = node_total_count + node_times[hr]
            if node_times[hr] != 0:
                node_hourly_output = node_hourly_output + red(str(node_times[hr])) + '|'
            else:
                node_hourly_output = node_hourly_output + str(node_times[hr]) + '|'
        print("\tJob Runs on Node \"" +  node + "\"\t = ", green(node_total_count))
        summary.write("\tJob Runs on Node \"" +  node + "\"\t = " + red(node_total_count) + '\n')
        print("\t\tNode Stats: Max Job Runs per Hr =", magenta(node_max_count) + ", Min Job Runs per Hr =", magenta(node_min_count) + ", 50th-percentile =", magenta(node_duration_p50) + ", 75th-percentile =", magenta(node_duration_p75))
        summary.write("\t\tNode Stats: Max Job Runs per Hr = " + magenta(node_max_count) + ", Min Job Runs per Hr = " + magenta(node_min_count) + ", 50th-percentile = " + magenta(node_duration_p50) + ", 75th-percentile = " + magenta(node_duration_p75) + '\n')
        print(node_hourly_output)
        summary.write(node_hourly_output + '\n')


    print('*' * 150)
    summary.write('*' * 150 + '\n')
    summary.close()


def user_friendly_time(hr):
    user_friendly_hr = ''
    if hr == '00':
        user_friendly_hr = '12 to 1 AM'
    elif hr == '01':
        user_friendly_hr = '1 to 2 AM'
    elif hr == '02':
        user_friendly_hr = '2 to 3 AM'
    elif hr == '03':
        user_friendly_hr = '3 to 4 AM'
    elif hr == '04':
        user_friendly_hr = '4 to 5 AM'
    elif hr == '05':
        user_friendly_hr = '5 to 6 AM'
    elif hr == '06':
        user_friendly_hr = '6 to 7 AM'
    elif hr == '07':
        user_friendly_hr = '7 to 8 AM'
    elif hr == '08':
        user_friendly_hr = '8 to 9 AM'
    elif hr == '09':
        user_friendly_hr = '9 to 10 AM'
    elif hr == '10':
        user_friendly_hr = '10 to 11 AM'
    elif hr == '11':
        user_friendly_hr = '11 to 12 PM'
    elif hr == '12':
        user_friendly_hr = '12 to 1 PM'
    elif hr == '13':
        user_friendly_hr = '1 to 2 PM'
    elif hr == '14':
        user_friendly_hr = '2 to 3 PM'
    elif hr == '15':
        user_friendly_hr = '3 to 4 PM'
    elif hr == '16':
        user_friendly_hr = '4 to 5 PM'
    elif hr == '17':
        user_friendly_hr = '5 to 6 PM'
    elif hr == '18':
        user_friendly_hr = '6 to 7 PM'
    elif hr == '19':
        user_friendly_hr = '7 to 8 PM'
    elif hr == '20':
        user_friendly_hr = '8 to 9 PM'
    elif hr == '21':
        user_friendly_hr = '9 to 10 PM'
    elif hr == '22':
        user_friendly_hr = '10 to 11 PM'
    elif hr == '23':
        user_friendly_hr = '11 to 12 AM'

    return user_friendly_hr


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
    tree = ET.parse(build_xml_file_name)
    root = tree.getroot()
    job_duration = 'Undef'
    job_builton = 'Undef'
    job_result = 'Undef'
    for child in root:
        if child.tag == 'duration':
            job_duration = child.text
        elif child.tag == 'builtOn':
            job_builton = child.text
        elif child.tag == 'result':
            job_result = child.text
    return job_duration, job_builton, job_result


def get_job_run_basics(job_run):
    line_tokens = job_run.split('/')
    job_key = get_job_key(line_tokens[:-3])
    job_name = line_tokens[-4]
    job_date_tokens = line_tokens[-2].split('_')
    job_date = job_date_tokens[0]
    job_time_tokens = job_date_tokens[1].split('-')
    job_time_hr = job_time_tokens[0]
    job_time_min = job_time_tokens[1]
    return job_key, job_name, job_date, job_time_hr, job_time_min


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
        print('Usage: {} <top-level-jobs-folder> <date-in-the-format: (YYYY-MM-DD)>'.format(sys.argv[0]))
        sys.exit(1)
    else:
        run_date = sys.argv[2]
        jobs_output_data_folder = os.getcwd() + '/ci-metrics-python/'
        if not os.path.exists(jobs_output_data_folder):
            os.makedirs(jobs_output_data_folder)
        top_level_folder_path = sys.argv[1]
        run_date = sys.argv[2]
        all_runs_file = os.getcwd() + '/all-runs.txt'
        generate_build_xml_file_list(top_level_folder_path, all_runs_file, run_date)
        process_build_xml_file_list(run_date, all_runs_file, jobs_output_data_folder)
