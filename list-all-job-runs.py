from __future__ import print_function
import datetime
import shlex
import sys
import os
import glob
from subprocess import Popen, PIPE
import xml.etree.ElementTree as ET

def generate_build_xml_file_list(top_level_folder_path, all_runs_file, run_date):
    # print("I am inside generate_build_xml_file_list")
    # print(top_level_folder_path, all_runs_file, run_date) 
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
    # print("I am inside process_build_xml_file_list")
    # print(run_date, all_runs_file, jobs_output_data_folder)

    # define variables to capture overall data
    total_num_of_jobs = 0
    nodes = {}

    # Process all build.xml files in all-runs.txt and set up dictionary of dictionaries data structure
    with open(all_runs_file, 'r') as file:
        for line in file:
            build_xml_file_name = line.strip()
            job_name, job_date, job_time_hr, job_time_min = get_job_run_basics(build_xml_file_name)
            job_duration, job_builton, job_result = process_build_xml_file(build_xml_file_name)
            print(job_name, job_date, job_time_hr, job_time_min, job_duration, job_builton, job_result)
            total_num_of_jobs = total_num_of_jobs + 1
            if job_builton not in nodes:
                nodes[job_builton] = {
                    '00': 0, '01': 0, '02': 0, '03': 0, '04': 0, '05': 0, '06': 0, '07': 0, '08': 0, '09': 0, '10': 0, '11': 0, '12': 0,
                    '13': 0, '14': 0, '15': 0, '16': 0, '17': 0, '18': 0, '19': 0, '20': 0, '21': 0, '22': 0, '23': 0
                }
            nodes[job_builton][job_time_hr] = nodes[job_builton][job_time_hr] + 1
    
    # Generate the node related metrics file for each node that ran a job on that day
    node_total_runs = {}
    for node, node_times in nodes.items():
        node_total_runs[node] = 0
        node_total_runs_count = 0
        node_file = open(jobs_output_data_folder + '/' + node + '.txt', 'w')
        for hr in sorted(node_times.keys()):
            node_total_runs_count = node_total_runs_count + node_times[hr]
            node_file.write(hr + ': ' + str(node_times[hr]) + '\n')
        node_total_runs[node] = node_total_runs_count
        node_file.close()
    
    # Generate summary report
    generate_ci_metrics_report(run_date, total_num_of_jobs, node_total_runs)

def generate_ci_metrics_report(run_date, total_num_of_jobs, node_total_runs):
    run_date_obj = datetime.datetime.strptime(run_date, '%Y-%m-%d').date()
    print('*' * 50)
    print("Date of CI Metrics Report Run:", run_date)
    print("Day of the week:", run_date_obj.strftime("%A"))
    print("Total Number of Job execution:", total_num_of_jobs)
    for node in sorted(node_total_runs.keys()):
        print("Total Number of Job executed on Node \"" +  node + "\":", node_total_runs[node])
    print('*' * 50)

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
    job_name = line_tokens[-4]
    job_date_tokens = line_tokens[-2].split('_')
    job_date = job_date_tokens[0]
    job_time_tokens = job_date_tokens[1].split('-')
    job_time_hr = job_time_tokens[0]
    job_time_min = job_time_tokens[1]
    return job_name, job_date, job_time_hr, job_time_min


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print('Usage: {} <top-level-jobs-folder> <date-in-the-format: (YYYY-MM-DD)>'.format(sys.argv[0]))
        sys.exit(1)
    else:
        run_date = sys.argv[2]
        jobs_output_data_folder = os.getcwd() + '/ci-metrics/' + run_date 
        if not os.path.exists(jobs_output_data_folder):
            os.makedirs(jobs_output_data_folder)
        top_level_folder_path = sys.argv[1]
        run_date = sys.argv[2]
        all_runs_file = os.getcwd() + '/all-runs.txt'
        generate_build_xml_file_list(top_level_folder_path, all_runs_file, run_date)
        process_build_xml_file_list(run_date, all_runs_file, jobs_output_data_folder)
