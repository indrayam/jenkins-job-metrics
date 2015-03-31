from __future__ import print_function, division
import os
import datetime
import time
import xml.etree.ElementTree as ET

__author__ = "Anand Sharma"

def parse_xml_file(build_xml_file_name):
    job_number, job_duration, job_builton, job_result, job_trigger, job_triggered_by, process_build_status = "Undef", "Undef", "Undef", "Undef", "Undef", "Undef", "_ERR_"
    if os.path.isfile(build_xml_file_name):
        process_build_status = "SUCCESS"
        tree = ET.parse(build_xml_file_name)
        root = tree.getroot()
        
        for child in root.iter('duration'):
            job_duration = child.text
            if job_duration is None:
                job_duration = ""
        
        for child in root.iter('builtOn'):
            job_builton = child.text
            if job_builton is None:
                job_builton = "Undef"
        
        for child in root.iter('result'):
            job_result = child.text
            if job_result is None:
                job_result = "Undef"
        
        for child in root.iter('number'):
            job_number = child.text
            if job_number is None:
                job_number = "Undef"

        for trigger in root.iter('hudson.model.Cause_-UserIdCause'):
            job_trigger = "Manual"
            for child in trigger:
                if child.tag == 'userId' and child.text is not None:
                    job_triggered_by = child.text

        for trigger in root.iter('hudson.triggers.TimerTrigger_-TimerTriggerCause'):
            job_trigger = "Scheduled"

        for trigger in root.iter('hudson.triggers.SCMTrigger_-SCMTriggerCause'):
            job_trigger = "SCM Triggered"

    return job_number, job_duration, job_builton, job_result, job_trigger, job_triggered_by, process_build_status


def process_build_xml_file_dump(top_level_folder_path, job_run_dump_file):
    all_job_runs = {}
    if os.path.isfile(job_run_dump_file):
        all_job_runs = populate_job_run_details_hash(job_run_dump_file)
    else:
        print("Dump file missing. Exiting..")
        sys.exit(1)
    job_run_file = open(job_run_dump_file, 'a')
    with open(all_runs_file, 'r') as file:
        for line in file:
            build_xml_file_name = line.strip()
            if build_xml_file_name not in all_job_runs:
                job_key, job_name, job_date, job_time_hr, job_time_min, job_run_basics_status = get_job_run_basics(
                    build_xml_file_name, top_level_folder_path)
                if job_run_basics_status == '_ERR_':
                    audit_log_file.write('_ERR_: File Path Parsing Error ' + build_xml_file_name + '\n')
                    continue
                job_number, job_duration, job_builton, job_result, job_trigger, job_triggered_by, process_build_status = parse_xml_file(
                    build_xml_file_name)
                if process_build_status == '_ERR_':
                    audit_log_file.write('_ERR_: File Does not Exist Error ' + build_xml_file_name + '\n')
                    continue
                job_url = get_job_url(job_key, job_number)
                audit_log_file.write(
                    job_key + '|' + job_number + '|' + job_date + '|' + job_time_hr + ':' + job_time_min + '|' + job_duration + '|' + job_builton + '|' + job_result + '|' + job_url + '|' + job_trigger + '|' + job_triggered_by + '\n')
                job_run_file.write(
                    build_xml_file_name + '|' + job_key + '|' + job_name + '|' + job_number + '|' + job_duration + '|' + job_builton + '|' + job_result + '|' + job_date + '|' + job_time_hr + '|' + job_time_min + '|' + job_url + '|' + job_trigger + '|' + job_triggered_by + '|' + "\n")

    audit_log_file.close()
    job_run_file.close()
    all_job_runs = populate_job_run_details_hash(job_run_dump_file)
    process_job_run_details_hash(run_date, run_timestamp, jobs_output_data_folder, all_jobs, all_job_runs, job_cron_type, encpwd)


def populate_job_run_details_hash(job_run_details_file):
    job_run_details_hash = {}
    with open(job_run_details_file, 'r') as job_run_file:
        for job_run_line in job_run_file:
            job_run_line = job_run_line.strip()
            job_run_tokens_list = job_run_line.split('|')
            job_run_details_hash[job_run_tokens_list[0]] = {'job_key': job_run_tokens_list[1],
                                                            'job_name': job_run_tokens_list[2],
                                                            'job_number': job_run_tokens_list[3],
                                                            'job_duration': job_run_tokens_list[4],
                                                            'job_builton': job_run_tokens_list[5],
                                                            'job_result': job_run_tokens_list[6],
                                                            'job_date': job_run_tokens_list[7],
                                                            'job_time_hr': job_run_tokens_list[8],
                                                            'job_time_min': job_run_tokens_list[9],
                                                            'job_url': job_run_tokens_list[10],
                                                            'job_trigger': job_run_tokens_list[11],
                                                            'job_triggered_by': job_run_tokens_list[12],
                                                            }
    return job_run_details_hash

def process_job_run_details_hash(jobs_output_data_folder, all_jobs, all_job_runs, job_cron_type, encpwd):
    # define variables to capture overall data
    total_num_of_job_runs = 0
    total_num_of_scheduled_job_runs = 0
    total_num_of_scm_triggered_job_runs = 0
    total_num_of_manual_job_runs = 0
    job_users = {}
    job_runs = {}
    job_runs_by_org = {}
    job_results = {}
    nodes = {}
    total_num_of_jobs_by_hr = {
        '00': 0, '01': 0, '02': 0, '03': 0, '04': 0, '05': 0, '06': 0, '07': 0, '08': 0, '09': 0, '10': 0, '11': 0,
        '12': 0,
        '13': 0, '14': 0, '15': 0, '16': 0, '17': 0, '18': 0, '19': 0, '20': 0, '21': 0, '22': 0, '23': 0
    }

    # Process all build.xml files in all-runs.txt and set up dictionary of dictionaries data structure
    for jk, jr in all_job_runs.items():
        build_xml_file_name = jr
        job_key = jr['job_key']
        job_name = jr['job_name']
        job_number = jr['job_number']
        job_duration = jr['job_duration']
        job_builton = jr['job_builton']
        job_result = jr['job_result']
        job_date = jr['job_date']
        job_time_hr = jr['job_time_hr']
        job_time_min = jr['job_time_min']
        job_url = jr['job_url']
        job_trigger = jr['job_trigger']
        job_triggered_by = jr['job_triggered_by']

        # Create a total count of all the jobs, scheduled and manual jobs
        total_num_of_job_runs = total_num_of_job_runs + 1
        if job_trigger == "Scheduled":
            total_num_of_scheduled_job_runs = total_num_of_scheduled_job_runs + 1
        elif job_trigger == "Manual":
            total_num_of_manual_job_runs = total_num_of_manual_job_runs + 1
            if job_triggered_by not in job_users:
                job_users[job_triggered_by] = 0
            job_users[job_triggered_by] = job_users[job_triggered_by] + 1
        elif job_trigger == "SCM Triggered":
            total_num_of_scm_triggered_job_runs = total_num_of_scm_triggered_job_runs + 1

        # Nodes Dictionary of Dictionaries
        if job_builton not in nodes:
            nodes[job_builton] = {
                'time': {
                    '00': 0, '01': 0, '02': 0, '03': 0, '04': 0, '05': 0, '06': 0, '07': 0, '08': 0, '09': 0, '10': 0,
                    '11': 0, '12': 0,
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

    # Store the number of users during this run
    job_users_log_file = open(jobs_output_data_folder + run_timestamp + '/' + 'job-users.log', 'w')
    for name, frequency in job_users.items():
        job_users_log_file.write(name + ': ' + str(frequency) + '\n')
    job_users_log_file.close()

def get_args():
    parser = argparse.ArgumentParser(
        description='Clean up the dump file for the date passed')
    parser.add_argument(
        '-d', '--date', type=str, help='Date (YYYY-MM-DD format) or use strings like \'today\', \'yesterday\'', required=True, default='today')

    args = parser.parse_args()
    date_str = args.date

    if date_str == 'today':
        date_obj = datetime.date.today()
        date_str = date_val.strftime('%Y-%m-%d')
    elif date_str == 'yesterday':
        date_obj = datetime.date.today() - datetime.timedelta(1)
        date_str = date_val.strftime('%Y-%m-%d')
    else:
        date_obj = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()

    return date_str, date_obj


if __name__ == "__main__":

    date_str, date_obj = get_args()

    run_date = date_obj.strftime('%Y-%m-%d')

    jobs_output_data_folder = os.getcwd() + '/ci-metrics-python/' + run_date + '/'
    if not os.path.exists(jobs_output_date_folder):
        os.makedirs(jobs_output_date_folder)

    job_run_details_file = jobs_output_data_folder + run_date + '-job-runs.dmp'

    process_build_xml_file_dump(jobs_output_data_folder, job_run_details_file)

