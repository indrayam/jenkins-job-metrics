from __future__ import print_function
import datetime
import time
import math
import shlex
import sys
import os
import glob
import smtplib
import re
from subprocess import Popen, PIPE
import xml.etree.ElementTree as ET
from color import red, green, yellow, blue, magenta, cyan, white
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def generate_config_xml_file_list(top_level_folder_path, all_jobs_file, run_date):
    cmd = 'ag -l --depth 50 -G \"config.xml\" \"<project>|</maven2-moduleset>\" ' + top_level_folder_path
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
            job_org_key = job_key.split(':')[0]
            if job_basics_status == '_ERR_':
                audit_job_log_file.write('_ERR_: File Path Parsing Error ' + config_xml_file_name + '\n')
                continue
            audit_job_log_file.write(job_key + '|' + job_name + '\n')
            # print('job_key', job_key, 'job_name', job_name)
            
            # Jobs Dictionary of Dictionary
            if job_key not in jobs:
                # Set up Name of the Job
                jobs[job_key] = {}
            
            # Setup Name of the Job
            jobs[job_key]['name'] = job_name

            # Setup Org of the Job
            jobs[job_key]['org'] = job_org_key

            # Setup Type of the Job
            # But first see if you can find PLSQL fragment
            tree = ET.parse(config_xml_file_name)
            root = tree.getroot()
            job_sonar_properties_text = "Undef"
            for artifact in root.iter('hudson.plugins.sonar.SonarRunnerBuilder'):
                for child in artifact:
                    if child.tag == 'properties':
                        job_sonar_properties_text = child.text
                        if job_sonar_properties_text is not None:
                            break
                        else:
                            job_sonar_properties_text = ''

            # And Ant fragment
            job_anttask_buildfile_text = "Undef"
            job_anttask_fragment = False
            for anttask in root.iter('hudson.tasks.Ant'):
                for child in anttask:
                    if child.tag == 'buildFile':
                        job_anttask_buildfile_text = child.text
                        if job_anttask_buildfile_text is not None:
                            job_anttask_fragment = True

            job_program_type = "Undef"
            if root.tag == 'project':
                    job_program_type = "Freestyle"
                    if re.search(r'.*plsql.*', job_sonar_properties_text, re.I):
                        job_program_type = job_program_type + " (w PLSQL)"
                    if job_anttask_fragment:
                        job_program_type = job_program_type + " (w Java/Ant)"
            elif root.tag == 'maven2-moduleset':
                job_program_type = "Java"
            jobs[job_key]['type'] = job_program_type

            # Setup Scheduled vs Unscheduled Type of the Job
            job_timer_spec = "Undef"
            for timer in root.iter('hudson.triggers.TimerTrigger'):
                job_timer_spec = timer[0].text
            spec_pattern = re.compile(r'#.*', re.I)
            if job_timer_spec == "Undef" or job_timer_spec is None:
                job_timer_spec = "Unscheduled"
            else:
                if spec_pattern.match(job_timer_spec):
                    job_timer_spec = "Scheduled+Inactive"
                else:
                    job_timer_spec = "Scheduled+Active"
            jobs[job_key]['timer'] = job_timer_spec

            # Setup Enabled vs Disabled Status of the Job
            job_status = "Undef"
            for status in root.iter('disabled'):
                job_status = status.text
            if re.match(r'false', job_status, re.I):
                job_status = "Enabled"
            elif re.match(r'true', job_status, re.I):
                job_status = "Disabled"
            jobs[job_key]['status'] = job_status

            # Setup SCM Status of the Job
            scm_feature = "Undef"
            for scm in root.iter('scm'):
                scm_class = scm.get('class')
            if re.match(r'.*SubversionSCM$', scm_class, re.I) and scm_class is not None:
                scm_feature = "Subversion"
            elif re.match(r'.*GitSCM$', scm_class, re.I) and scm_class is not None:
                scm_feature = "Git"
            elif re.match(r'.*NullSCM$', scm_class, re.I) and scm_class is not None:
                scm_feature = "No SCM"
            jobs[job_key]['scm'] = scm_feature

            # Setup Artifactory Configuration of the Job
            artifact_feature = "Undef"
            for artifact in root.iter('org.jfrog.hudson.ArtifactoryRedeployPublisher'):
                artifact_feature = "Enabled"
            if artifact_feature == "Undef":
                artifact_feature = "Disabled"
            jobs[job_key]['artifactory'] = artifact_feature

            # Setup Sonar Quality Scan Configuration of the Job
            sonar_feature = "Undef"
            for artifact in root.iter('hudson.plugins.sonar.SonarRunnerBuilder'):
                sonar_feature = "Enabled"
            if sonar_feature == "Undef":
                sonar_feature = "Disabled"
            jobs[job_key]['sonar'] = sonar_feature

            # Setup Appscan Configuration of the Job
            appscan_feature = "Disabled"
            for scan in root.iter('goals'):
                if scan.text is not None:
                    if re.search(r'.*appscan.*', scan.text, re.I):
                        appscan_feature = "Enabled"
            jobs[job_key]['appscan'] = appscan_feature

            # Setup CDD Configuration of the Job
            cdd_feature = "Disabled"
            for cdd in root.iter('hudson.plugins.postbuildtask.TaskProperties'):
                for child in cdd:
                    if child.tag == 'script' and child.text is not None:
                        if re.search(r'CIMVService', child.text, re.I):
                            cdd_feature = "Enabled"
            jobs[job_key]['cdd'] = cdd_feature

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

def html_header(run_date):
    header = """\
<html>
<head>
<title>CI Job Run Summary Report</title>
<style>
pre {
    font-family: calibri, arial, sans-serif;
    font-size: 1.1em;
    border-style: dashed;
    border-width: 1px;
    background-color: #ececec;
    border-color: gray;
    overflow: auto;
}
h1 {
    font-family: cambria, serif;
    font-size: 1.5em;
    color: black;   
}
</style>
</head>
<body>
<h1>CI Job Metrics for """
    header = header + run_date + "</h1><pre>\n"
    return header


def html_footer():
    footer = """\
</body>
</html>
"""
    return footer


def generate_ci_metrics_report(run_date, run_timestamp, all_jobs, total_num_of_job_runs, nodes, job_runs, job_results, job_runs_by_org, total_num_of_jobs_by_hr):
    # print(all_jobs)

    run_date_obj = datetime.datetime.strptime(run_date, '%Y-%m-%d').date()
    jobs_summary_report_filename = get_summary_report_filename(jobs_output_data_folder, run_date, run_timestamp)

    ci_metrics_report = '*' * 150 + "\n"
    ci_metrics_report_plain = ci_metrics_report

    today = datetime.date.today()
    stoday = today.strftime('%Y-%m-%d')
    ci_metrics_report_html = html_header(stoday)
    fragmentj1 = "Date of CI Job Metrics Report: " + yellow(stoday) + "\n"
    pfragmentj1 = "Date of CI Job Metrics Report: " + str(stoday) + "\n"
    hfragmentj1 = "<strong style=\"color: navy\">Date of CI Job Metrics Report:</strong> " + "<strong style=\"color: blue\">" + str(stoday) + "</strong>" + "\n"
    ci_metrics_report = ci_metrics_report + fragmentj1
    ci_metrics_report_plain = ci_metrics_report_plain + pfragmentj1
    ci_metrics_report_html = ci_metrics_report_html + hfragmentj1

    fragmentj2 = "Day of the week: " + today.strftime("%A") + "\n"
    ci_metrics_report = ci_metrics_report + fragmentj2
    hfragmentj2 = "<strong style=\"color: navy\">Day of the week:</strong> " + today.strftime("%A") + "\n"
    ci_metrics_report_plain = ci_metrics_report_plain + fragmentj2
    ci_metrics_report_html = ci_metrics_report_html + hfragmentj2

    total_num_of_jobs = 0
    all_jobs_by_org_count = {}
    all_jobs_by_type_count = {}
    all_jobs_by_status_count = {}
    all_jobs_by_timer_count = {}
    all_jobs_by_scm_count = {}
    all_jobs_by_artifactory_count = {}
    all_jobs_by_sonar_count = {}
    all_jobs_by_appscan_count = {}
    all_jobs_by_cdd_count = {}
    for job_key, job_details in all_jobs.items():
        total_num_of_jobs = total_num_of_jobs + 1 

        if job_details['org'] not in all_jobs_by_org_count:
            all_jobs_by_org_count[job_details['org']] = 1
        else:
            all_jobs_by_org_count[job_details['org']] = all_jobs_by_org_count[job_details['org']] + 1

        if job_details['type'] not in all_jobs_by_type_count:
            all_jobs_by_type_count[job_details['type']] = 1
        else:
            all_jobs_by_type_count[job_details['type']] = all_jobs_by_type_count[job_details['type']] + 1

        if job_details['status'] not in all_jobs_by_status_count:
            all_jobs_by_status_count[job_details['status']] = 1
        else:
            all_jobs_by_status_count[job_details['status']] = all_jobs_by_status_count[job_details['status']] + 1

        if job_details['timer'] not in all_jobs_by_timer_count:
            all_jobs_by_timer_count[job_details['timer']] = 1
        else:
            all_jobs_by_timer_count[job_details['timer']] = all_jobs_by_timer_count[job_details['timer']] + 1

        if job_details['scm'] not in all_jobs_by_scm_count:
            all_jobs_by_scm_count[job_details['scm']] = 1
        else: 
            all_jobs_by_scm_count[job_details['scm']] = all_jobs_by_scm_count[job_details['scm']] + 1

        if job_details['artifactory'] not in all_jobs_by_artifactory_count:
            all_jobs_by_artifactory_count[job_details['artifactory']] = 1
        else: 
            all_jobs_by_artifactory_count[job_details['artifactory']] = all_jobs_by_artifactory_count[job_details['artifactory']] + 1

        if job_details['sonar'] not in all_jobs_by_sonar_count:
            all_jobs_by_sonar_count[job_details['sonar']] = 1
        else: 
            all_jobs_by_sonar_count[job_details['sonar']] = all_jobs_by_sonar_count[job_details['sonar']] + 1

        if job_details['appscan'] not in all_jobs_by_appscan_count:
            all_jobs_by_appscan_count[job_details['appscan']] = 1
        else: 
            all_jobs_by_appscan_count[job_details['appscan']] = all_jobs_by_appscan_count[job_details['appscan']] + 1

        if job_details['cdd'] not in all_jobs_by_cdd_count:
            all_jobs_by_cdd_count[job_details['cdd']] = 1
        else:
            all_jobs_by_cdd_count[job_details['cdd']] = all_jobs_by_cdd_count[job_details['cdd']] + 1

    # print('By Org', all_jobs_by_org_count)
    # print('By Type', all_jobs_by_type_count)
    # print('By Status', all_jobs_by_status_count)
    # print('By Timer', all_jobs_by_timer_count)
    # print('By SCM', all_jobs_by_scm_count)
    # print('By Artifactory', all_jobs_by_artifactory_count)
    # print('By Sonar', all_jobs_by_sonar_count)
    # print('By Appscan', all_jobs_by_appscan_count)
    # print('By CDD', all_jobs_by_cdd_count)
    today = datetime.date.today()
    stoday = today.strftime('%Y-%m-%d')
    fragmentj3 = "Total Number of Unique Jobs in CI: " + green(total_num_of_jobs) + "\n"
    pfragmentj3 = "Total Number of Unique Jobs in CI: " + str(total_num_of_jobs) + "\n"
    hfragmentj3 = "<strong style=\"color: navy\">Total Number of Unique Jobs in CI:</strong> " + "<strong style=\"color: green\">" + str(total_num_of_jobs) + "</strong>" + "\n"
    ci_metrics_report = ci_metrics_report + fragmentj3
    ci_metrics_report_plain = ci_metrics_report_plain + pfragmentj3
    ci_metrics_report_html = ci_metrics_report_html + hfragmentj3

    fragmentj4 = "\tBy Job Org:\n"
    hfragmentj4 = "\t<span style=\" color: maroon\">By Job Org:</span>\n"
    ci_metrics_report = ci_metrics_report + fragmentj4
    ci_metrics_report_plain = ci_metrics_report_plain + fragmentj4
    ci_metrics_report_html = ci_metrics_report_html + hfragmentj4
    all_jobs_by_org_output = '\t\t'
    pall_jobs_by_org_output = '\t\t'
    hall_jobs_by_org_output = '\t\t'
    org_count_index = 0
    for job_org, job_org_count in sorted(all_jobs_by_org_count.iteritems(), key=lambda (k,v): (v, k), reverse=True):
            if org_count_index < 3:
                if job_org_count > 50:
                    all_jobs_by_org_output = all_jobs_by_org_output + job_org + ' = ' + green(job_org_count) + ', '
                    pall_jobs_by_org_output = pall_jobs_by_org_output + job_org + ' = ' + str(job_org_count) + ', '
                    hall_jobs_by_org_output = hall_jobs_by_org_output + job_org + ' = ' + "<b>" + str(job_org_count) + "</b>" + ', '
                else:
                    all_jobs_by_org_output = all_jobs_by_org_output + job_org + ' = ' + str(job_org_count) + ', '
                    pall_jobs_by_org_output = pall_jobs_by_org_output + job_org + ' = ' + str(job_org_count) + ', '
                    hall_jobs_by_org_output = hall_jobs_by_org_output + job_org + ' = ' + str(job_org_count) + ', '
                org_count_index = org_count_index + 1
            else:
                org_count_index = 0
                if job_org_count > 50:
                    all_jobs_by_org_output = all_jobs_by_org_output.strip(', ') + "\n\t\t" + job_org + ' = ' + green(job_org_count) + ', '
                    pall_jobs_by_org_output = pall_jobs_by_org_output.strip(', ') + "\n\t\t" + job_org + ' = ' + str(job_org_count) + ', '
                    hall_jobs_by_org_output = hall_jobs_by_org_output.strip(', ') + "\n\t\t" + job_org + ' = ' + "<b>" + str(job_org_count) + "</b>" + ', '
                else:
                    all_jobs_by_org_output = all_jobs_by_org_output.strip(', ') + "\n\t\t" + job_org + ' = ' + str(job_org_count) + ', '
                    pall_jobs_by_org_output = pall_jobs_by_org_output.strip(', ') + "\n\t\t" + job_org + ' = ' + str(job_org_count) + ', '
                    hall_jobs_by_org_output = hall_jobs_by_org_output.strip(', ') + "\n\t\t" + job_org + ' = ' + str(job_org_count) + ', '
                org_count_index = org_count_index + 1
    all_jobs_by_org_output = all_jobs_by_org_output.strip(', ') + "\n"
    pall_jobs_by_org_output = pall_jobs_by_org_output.strip(', ') + "\n"
    hall_jobs_by_org_output = hall_jobs_by_org_output.strip(', ') + "\n"
    ci_metrics_report = ci_metrics_report + all_jobs_by_org_output
    ci_metrics_report_plain = ci_metrics_report_plain + pall_jobs_by_org_output
    ci_metrics_report_html = ci_metrics_report_html + hall_jobs_by_org_output

    fragmentj5 = "\tBy Job Type: "
    hfragmentj5 = "\t<span style=\" color: maroon\">By Job Type:</span> "
    ci_metrics_report = ci_metrics_report + fragmentj5
    ci_metrics_report_plain = ci_metrics_report_plain + fragmentj5
    ci_metrics_report_html = ci_metrics_report_html + hfragmentj5
    all_jobs_by_type_output = ''
    pall_jobs_by_type_output = ''
    hall_jobs_by_type_output = ''
    for job_type, job_type_count in all_jobs_by_type_count.items():
        all_jobs_by_type_output = all_jobs_by_type_output + job_type + ' = ' + str(job_type_count) + ', '
        pall_jobs_by_type_output = pall_jobs_by_type_output + job_type + ' = ' + str(job_type_count) + ', '
        hall_jobs_by_type_output = hall_jobs_by_type_output + job_type + ' = ' + str(job_type_count) + ', '
    all_jobs_by_type_output = all_jobs_by_type_output.strip(', ') + "\n"
    pall_jobs_by_type_output = pall_jobs_by_type_output.strip(', ') + "\n"
    hall_jobs_by_type_output = hall_jobs_by_type_output.strip(', ') + "\n"
    ci_metrics_report = ci_metrics_report + all_jobs_by_type_output
    ci_metrics_report_plain = ci_metrics_report_plain + pall_jobs_by_type_output
    ci_metrics_report_html = ci_metrics_report_html + hall_jobs_by_type_output

    fragmentj6 = "\tBy Job Status: "
    hfragmentj6 = "\t<span style=\" color: maroon\">By Job Status:</span> "
    ci_metrics_report = ci_metrics_report + fragmentj6
    ci_metrics_report_plain = ci_metrics_report_plain + fragmentj6
    ci_metrics_report_html = ci_metrics_report_html + hfragmentj6
    all_jobs_by_status_output = ''
    pall_jobs_by_status_output = ''
    hall_jobs_by_status_output = ''
    for job_status, job_status_count in all_jobs_by_status_count.items():
        all_jobs_by_status_output = all_jobs_by_status_output + job_status + ' = ' + str(job_status_count) + ', '
        pall_jobs_by_status_output = pall_jobs_by_status_output + job_status + ' = ' + str(job_status_count) + ', '
        hall_jobs_by_status_output = hall_jobs_by_status_output + job_status + ' = ' + str(job_status_count) + ', '
    all_jobs_by_status_output = all_jobs_by_status_output.strip(', ') + "\n"
    pall_jobs_by_status_output = pall_jobs_by_status_output.strip(', ') + "\n"
    hall_jobs_by_status_output = hall_jobs_by_status_output.strip(', ') + "\n"
    ci_metrics_report = ci_metrics_report + all_jobs_by_status_output
    ci_metrics_report_plain = ci_metrics_report_plain + pall_jobs_by_status_output
    ci_metrics_report_html = ci_metrics_report_html + hall_jobs_by_status_output

    fragmentj7 = "\tBy Job Schedule Type: "
    hfragmentj7 = "\t<span style=\" color: maroon\">By Job Schedule Type:</span> "
    ci_metrics_report = ci_metrics_report + fragmentj7
    ci_metrics_report_plain = ci_metrics_report_plain + fragmentj7
    ci_metrics_report_html = ci_metrics_report_html + hfragmentj7
    all_jobs_by_timer_output = ''
    pall_jobs_by_timer_output = ''
    hall_jobs_by_timer_output = ''
    for job_timer, job_timer_count in all_jobs_by_timer_count.items():
        all_jobs_by_timer_output = all_jobs_by_timer_output + job_timer + ' = ' + str(job_timer_count) + ', '
        pall_jobs_by_timer_output = pall_jobs_by_timer_output + job_timer + ' = ' + str(job_timer_count) + ', '
        hall_jobs_by_timer_output = hall_jobs_by_timer_output + job_timer + ' = ' + str(job_timer_count) + ', '
    all_jobs_by_timer_output = all_jobs_by_timer_output.strip(', ') + "\n"
    pall_jobs_by_timer_output = pall_jobs_by_timer_output.strip(', ') + "\n"
    hall_jobs_by_timer_output = hall_jobs_by_timer_output.strip(', ') + "\n"
    ci_metrics_report = ci_metrics_report + all_jobs_by_timer_output
    ci_metrics_report_plain = ci_metrics_report_plain + pall_jobs_by_timer_output
    ci_metrics_report_html = ci_metrics_report_html + hall_jobs_by_timer_output

    fragmentj8 = "\tBy Job SCM Type: "
    hfragmentj8 = "\t<span style=\" color: maroon\">By Job SCM Type:</span> "
    ci_metrics_report = ci_metrics_report + fragmentj8
    ci_metrics_report_plain = ci_metrics_report_plain + fragmentj8
    ci_metrics_report_html = ci_metrics_report_html + hfragmentj8
    all_jobs_by_scm_output = ''
    pall_jobs_by_scm_output = ''
    hall_jobs_by_scm_output = ''
    for job_scm, job_scm_count in all_jobs_by_scm_count.items():
        all_jobs_by_scm_output = all_jobs_by_scm_output + job_scm + ' = ' + str(job_scm_count) + ', '
        pall_jobs_by_scm_output = pall_jobs_by_scm_output + job_scm + ' = ' + str(job_scm_count) + ', '
        hall_jobs_by_scm_output = hall_jobs_by_scm_output + job_scm + ' = ' + str(job_scm_count) + ', '
    all_jobs_by_scm_output = all_jobs_by_scm_output.strip(', ') + "\n"
    pall_jobs_by_scm_output = pall_jobs_by_scm_output.strip(', ') + "\n"
    hall_jobs_by_scm_output = hall_jobs_by_scm_output.strip(', ') + "\n"
    ci_metrics_report = ci_metrics_report + all_jobs_by_scm_output
    ci_metrics_report_plain = ci_metrics_report_plain + pall_jobs_by_scm_output
    ci_metrics_report_html = ci_metrics_report_html + hall_jobs_by_scm_output

    fragmentj9 = "\tBy Job Sonar Quality Scan Feature: "
    hfragmentj9 = "\t<span style=\" color: maroon\">By Job Sonar Quality Scan Feature:</span> "
    ci_metrics_report = ci_metrics_report + fragmentj9
    ci_metrics_report_plain = ci_metrics_report_plain + fragmentj9
    ci_metrics_report_html = ci_metrics_report_html + hfragmentj9
    all_jobs_by_sonar_output = ''
    pall_jobs_by_sonar_output = ''
    hall_jobs_by_sonar_output = ''
    for job_sonar, job_sonar_count in all_jobs_by_sonar_count.items():
        all_jobs_by_sonar_output = all_jobs_by_sonar_output + job_sonar + ' = ' + str(job_sonar_count) + ', '
        pall_jobs_by_sonar_output = pall_jobs_by_sonar_output + job_sonar + ' = ' + str(job_sonar_count) + ', '
        hall_jobs_by_sonar_output = hall_jobs_by_sonar_output + job_sonar + ' = ' + str(job_sonar_count) + ', '
    all_jobs_by_sonar_output = all_jobs_by_sonar_output.strip(', ') + "\n"
    pall_jobs_by_sonar_output = pall_jobs_by_sonar_output.strip(', ') + "\n"
    hall_jobs_by_sonar_output = hall_jobs_by_sonar_output.strip(', ') + "\n"
    ci_metrics_report = ci_metrics_report + all_jobs_by_sonar_output
    ci_metrics_report_plain = ci_metrics_report_plain + pall_jobs_by_sonar_output
    ci_metrics_report_html = ci_metrics_report_html + hall_jobs_by_sonar_output

    fragmentj10 = "\tBy Job Appscan Feature: "
    hfragmentj10 = "\t<span style=\" color: maroon\">By Job Appscan Feature:</span> "
    ci_metrics_report = ci_metrics_report + fragmentj10
    ci_metrics_report_plain = ci_metrics_report_plain + fragmentj10
    ci_metrics_report_html = ci_metrics_report_html + hfragmentj10
    all_jobs_by_appscan_output = ''
    pall_jobs_by_appscan_output = ''
    hall_jobs_by_appscan_output = ''
    for job_appscan, job_appscan_count in all_jobs_by_appscan_count.items():
        all_jobs_by_appscan_output = all_jobs_by_appscan_output + job_appscan + ' = ' + str(job_appscan_count) + ', '
        pall_jobs_by_appscan_output = pall_jobs_by_appscan_output + job_appscan + ' = ' + str(job_appscan_count) + ', '
        hall_jobs_by_appscan_output = hall_jobs_by_appscan_output + job_appscan + ' = ' + str(job_appscan_count) + ', '
    all_jobs_by_appscan_output = all_jobs_by_appscan_output.strip(', ') + "\n"
    pall_jobs_by_appscan_output = pall_jobs_by_appscan_output.strip(', ') + "\n"
    hall_jobs_by_appscan_output = hall_jobs_by_appscan_output.strip(', ') + "\n"
    ci_metrics_report = ci_metrics_report + all_jobs_by_appscan_output
    ci_metrics_report_plain = ci_metrics_report_plain + pall_jobs_by_appscan_output
    ci_metrics_report_html = ci_metrics_report_html + hall_jobs_by_appscan_output

    ci_metrics_report = ci_metrics_report + '*' * 150 + "\n"
    ci_metrics_report_plain = ci_metrics_report_plain + '*' * 150 + "\n"
    ci_metrics_report_html = ci_metrics_report_html + "</pre>" + "\n"

    ci_metrics_report = ci_metrics_report + "\n"
    ci_metrics_report_plain = ci_metrics_report_plain + "\n"
    ci_metrics_report_html = ci_metrics_report_html + "<h1>CI Job Run Metrics for " + run_date + "</h1><pre>\n"

    ci_metrics_report = ci_metrics_report + '*' * 150 + "\n"
    ci_metrics_report_plain = ci_metrics_report_plain + '*' * 150 + "\n"

    fragment1 = "Date of CI Job Run Metrics Report: " + yellow(run_date) + "\n"
    pfragment1 = "Date of CI Job Run Metrics Report: " + str(run_date) + "\n"
    hfragment1 = "<strong style=\"color: navy\">Date of CI Job Run Metrics Report:</strong> " + "<strong style=\"color: blue\">" + str(run_date) + "</strong>" + "\n"
    ci_metrics_report = ci_metrics_report + fragment1
    ci_metrics_report_plain = ci_metrics_report_plain + pfragment1
    ci_metrics_report_html = ci_metrics_report_html + hfragment1

    fragment2 = "Day of the week: " + run_date_obj.strftime("%A") + "\n"
    hfragment2 = "<strong style=\"color: navy\">Day of the week:</strong> " + run_date_obj.strftime("%A") + "\n"
    ci_metrics_report = ci_metrics_report + fragment2
    ci_metrics_report_plain = ci_metrics_report_plain + fragment2
    ci_metrics_report_html = ci_metrics_report_html + hfragment2

    fragment3 = "Total Number of Job Runs: " + green(total_num_of_job_runs) + "\n"
    pfragment3 = "Total Number of Job Runs: " + str(total_num_of_job_runs) + "\n"
    hfragment3 = "<strong style=\"color: navy\">Total Number of Job Runs:</strong> " + "<strong style=\"color: green\">" + str(total_num_of_job_runs) + "</strong>" + "\n"
    ci_metrics_report = ci_metrics_report + fragment3
    ci_metrics_report_plain = ci_metrics_report_plain + pfragment3
    ci_metrics_report_html = ci_metrics_report_html + hfragment3
    
    fragment4 = "\tJob Run Count By Build Status: "
    hfragment4 = "\t<span style=\" color: maroon\">By Job Run Count By Build Status:</span> "
    ci_metrics_report = ci_metrics_report + fragment4
    ci_metrics_report_plain = ci_metrics_report_plain + fragment4
    ci_metrics_report_html = ci_metrics_report_html + hfragment4
    job_result_output = ''
    pjob_result_output = ''
    hjob_result_output = ''
    for job_result_type, job_result_frequency in job_results.items():
        if job_result_type == 'SUCCESS':
            job_result_output = job_result_output + job_result_type + ' = ' + green(job_result_frequency) + ', '
        else:
            job_result_output = job_result_output + job_result_type + ' = ' + red(job_result_frequency) + ', '
        pjob_result_output = pjob_result_output + job_result_type + ' = ' + str(job_result_frequency) + ', '
        hjob_result_output = hjob_result_output + job_result_type + ' = ' + str(job_result_frequency) + ', '
    job_result_output = job_result_output.strip(', ') + "\n"
    pjob_result_output = pjob_result_output.strip(', ') + "\n"
    hjob_result_output = hjob_result_output.strip(', ') + "\n"
    ci_metrics_report = ci_metrics_report + job_result_output
    ci_metrics_report_plain = ci_metrics_report_plain + pjob_result_output
    ci_metrics_report_html = ci_metrics_report_html + hjob_result_output

    fragment5 = "\tJob Run Timeline (PST): |"
    hfragment5 = "\t<span style=\" color: maroon\">By Job Run Timeline:</span> |"
    ci_metrics_report = ci_metrics_report + fragment5
    ci_metrics_report_plain = ci_metrics_report_plain + fragment5
    ci_metrics_report_html = ci_metrics_report_html + hfragment5
    overall_job_run_timeline_output = ''
    poverall_job_run_timeline_output = ''
    hoverall_job_run_timeline_output = ''
    for hr in sorted(total_num_of_jobs_by_hr.keys()):
        if total_num_of_jobs_by_hr[hr] > 12:
            overall_job_run_timeline_output = overall_job_run_timeline_output + red(str(total_num_of_jobs_by_hr[hr])) + '|'
            hoverall_job_run_timeline_output = hoverall_job_run_timeline_output + "<span style=\"color: red\">" + str(total_num_of_jobs_by_hr[hr]) + '</span>|'
        else:
            overall_job_run_timeline_output = overall_job_run_timeline_output + str(total_num_of_jobs_by_hr[hr]) + '|'
            hoverall_job_run_timeline_output = hoverall_job_run_timeline_output + str(total_num_of_jobs_by_hr[hr]) + '|'
        poverall_job_run_timeline_output = poverall_job_run_timeline_output + str(total_num_of_jobs_by_hr[hr]) + '|'
    ci_metrics_report = ci_metrics_report + overall_job_run_timeline_output + "\n"
    ci_metrics_report_plain = ci_metrics_report_plain + poverall_job_run_timeline_output + "\n"
    ci_metrics_report_html = ci_metrics_report_html + hoverall_job_run_timeline_output + "\n"

    fragment6 = "\tJobs That Ran: " + green(len(job_runs)) + "\n"
    pfragment6 = "\tJobs That Ran: " + str(len(job_runs)) + "\n"
    hfragment6 = "\t<span style=\" color: maroon\">Jobs That Ran:</span> " + "<strong style=\"color: green\">" + str(len(job_runs)) + "</strong>" + "\n"
    ci_metrics_report = ci_metrics_report + fragment6
    ci_metrics_report_plain = ci_metrics_report_plain + pfragment6
    ci_metrics_report_html = ci_metrics_report_html + hfragment6
 
    fragment7 = "Top 5 Orgs, by Job Runs:" + "\n"
    hfragment7 = "<strong style=\"color: navy\">Top 5 Orgs, by Job Runs:</strong> " + "\n"
    ci_metrics_report = ci_metrics_report + fragment7
    ci_metrics_report_plain = ci_metrics_report_plain + fragment7
    ci_metrics_report_html = ci_metrics_report_html + hfragment7
    job_org_count = 0
    top5_orgs_output = ''
    ptop5_orgs_output = ''
    htop5_orgs_output = ''
    for job_org, job_org_run in sorted(job_runs_by_org.iteritems(), key=lambda (k,v): (v, k), reverse=True):
        job_org_count = job_org_count + 1
        if job_org_count < 6:
            if job_org_count == 1:
                top5_orgs_output = top5_orgs_output + "\t" + job_org + " = " + green(job_org_run) + "\n"
                htop5_orgs_output = htop5_orgs_output + "\t" + job_org + " = " + "<span style=\"color: green\">" + str(job_org_run) + "</span>" + "\n"
            else:
                top5_orgs_output = top5_orgs_output + "\t" + job_org + " = " + str(job_org_run) + "\n"
                htop5_orgs_output = htop5_orgs_output + "\t" + job_org + " = " +  str(job_org_run) + "\n"
            ptop5_orgs_output = ptop5_orgs_output + "\t" + job_org + " = " + str(job_org_run) + "\n"
    ci_metrics_report = ci_metrics_report + top5_orgs_output
    ci_metrics_report_plain = ci_metrics_report_plain + ptop5_orgs_output
    ci_metrics_report_html = ci_metrics_report_html + htop5_orgs_output

    fragment8 = "Top 5 Jobs, by Job Runs:" + "\n"
    hfragment8 = "<strong style=\"color: navy\">Top 5 Jobs, by Job Runs:</strong> " + "\n"
    ci_metrics_report = ci_metrics_report + fragment8
    ci_metrics_report_plain = ci_metrics_report_plain + fragment8
    ci_metrics_report_html = ci_metrics_report_html + hfragment8
    top5_jobs_output = ''
    ptop5_jobs_output = ''
    htop5_jobs_output = ''
    job_count = 0
    for job, job_run in sorted(job_runs.iteritems(), key=lambda (k,v): (v, k), reverse=True):
        job_count = job_count + 1
        if job_count < 6:
            if job_count == 1:
                top5_jobs_output = top5_jobs_output + "\t" + job + " = " + green(job_run) + "\n"
                htop5_jobs_output = htop5_jobs_output + "\t" + job + " = " + "<span style=\"color: green\">" + str(job_run) + "</span>" + "\n"
            else:
                top5_jobs_output = top5_jobs_output + "\t" + job + " = " + str(job_run) + "\n"
                htop5_jobs_output = htop5_jobs_output + "\t" + job + " = " +  str(job_run) + "\n"
            ptop5_jobs_output = ptop5_jobs_output + "\t" + job + " = " + str(job_run) + "\n"
    ci_metrics_report = ci_metrics_report + top5_jobs_output
    ci_metrics_report_plain = ci_metrics_report_plain + ptop5_jobs_output
    ci_metrics_report_html = ci_metrics_report_html + htop5_jobs_output

    fragment9 = "Job Run Details, By Nodes:" + "\n"
    hfragment9 = "<strong style=\"color: navy\">Job Run Details, By Nodes:</strong> " + "\n"
    ci_metrics_report = ci_metrics_report + fragment9
    ci_metrics_report_plain = ci_metrics_report_plain + fragment9
    ci_metrics_report_html = ci_metrics_report_html + hfragment9
    for node, node_stats_type in nodes.items():
        node_total_count = 0

        node_times_values = node_stats_type['time'].values()
        node_max_count = max(node_times_values)
        node_min_count = min(node_times_values)
        node_count_p50, node_count_p75 = get_percentiles(node_times_values)
        node_hourly_output = '\t\tJob Run Timeline (PST): |'
        pnode_hourly_output = '\t\tJob Run Timeline (PST): |'
        hnode_hourly_output = '\t\t<i>Job Run Timeline (PST):</i> |'
        for hr in sorted(node_stats_type['time'].keys()):
            node_total_count = node_total_count + node_stats_type['time'][hr]
            if node_stats_type['time'][hr] != 0 and node_stats_type['time'][hr] > 12:
                node_hourly_output = node_hourly_output + red(str(node_stats_type['time'][hr])) + '|'
                hnode_hourly_output = hnode_hourly_output + "<span style=\"color: red\">" + str(node_stats_type['time'][hr]) + "</span>" + '|'
            else:
                node_hourly_output = node_hourly_output + str(node_stats_type['time'][hr]) + '|'
                hnode_hourly_output = hnode_hourly_output + str(node_stats_type['time'][hr]) +  '|'
            pnode_hourly_output = pnode_hourly_output + str(node_stats_type['time'][hr]) + '|'
        node_hourly_output = node_hourly_output + "\n"
        pnode_hourly_output = pnode_hourly_output + "\n"
        hnode_hourly_output = hnode_hourly_output + "\n"

        # Job Run Count Output By Node
        fragment10 = "\tTotal Job Runs on Node \"" +  node + "\" = " + green(node_total_count) + "\n"
        pfragment10 = "\tTotal Job Runs on Node \"" +  node + "\" = " + str(node_total_count) + "\n"
        hfragment10 = "\t<span style=\"color: maroon\">Total Job Runs on Node <strong>" +  node + "</strong></span> = " + "<span style=\"color: green\">" + str(node_total_count) + "</span>" + "\n"
        ci_metrics_report = ci_metrics_report + fragment10
        ci_metrics_report_plain = ci_metrics_report_plain + pfragment10
        ci_metrics_report_html = ci_metrics_report_html + hfragment10
        node_count_stats_output = "\t\tJob Run Count Stats: Max Job Runs per Hr = " + magenta(node_max_count) + ", Min Job Runs per Hr = " + magenta(node_min_count) + ", 50th-percentile = " + magenta(node_count_p50) + ", 75th-percentile = " + magenta(node_count_p75) + "\n"
        pnode_count_stats_output = "\t\tJob Run Count Stats: Max Job Runs per Hr = " + str(node_max_count) + ", Min Job Runs per Hr = " + str(node_min_count) + ", 50th-percentile = " + str(node_count_p50) + ", 75th-percentile = " + str(node_count_p75) + "\n"
        hnode_count_stats_output = "\t\t<i>Job Run Count Stats:</i> Max Job Runs per Hr = " + "<span style=\"color: teal\">" + str(node_max_count) + "</span>, Min Job Runs per Hr = " + "<span style=\"color: teal\">" + str(node_min_count) + "</span>, 50th-percentile = " + "<span style=\"color: teal\">" + str(node_count_p50) + "</span>, 75th-percentile = " + "<span style=\"color: teal\">" + str(node_count_p75) + "</span>\n"
        ci_metrics_report = ci_metrics_report + node_count_stats_output
        ci_metrics_report_plain = ci_metrics_report_plain + pnode_count_stats_output
        ci_metrics_report_html = ci_metrics_report_html + hnode_count_stats_output
        
        # Build Status Count Output By Node
        node_status_output = '\t\tJob Run Count By Build Status: '
        pnode_status_output = '\t\tJob Run Count By Build Status: '
        hnode_status_output = '\t\t<i>Job Run Count By Build Status:</i> '
        for st in node_stats_type['status'].keys():
            node_status_output = node_status_output + st + ' = ' + blue(node_stats_type['status'][st]) + ', '
            pnode_status_output = pnode_status_output + st + ' = ' + str(node_stats_type['status'][st]) + ', '
            hnode_status_output = hnode_status_output + st + ' = ' + "<span style=\"color: teal\">" + str(node_stats_type['status'][st]) + "</span>" + ', '
        node_status_output = node_status_output.strip(', ') + "\n"
        pnode_status_output = pnode_status_output.strip(', ') + "\n"
        hnode_status_output = hnode_status_output.strip(', ') + "\n"
        ci_metrics_report = ci_metrics_report + node_status_output
        ci_metrics_report_plain = ci_metrics_report_plain + pnode_status_output
        ci_metrics_report_html = ci_metrics_report_html + hnode_status_output

        # Duration Stats Output By Node
        node_duration_values = list(node_stats_type['duration'].values())
        if len(node_duration_values) > 0:
            node_max_duration_msec = max(node_duration_values)
            node_max_duration = user_friendly_secs(node_max_duration_msec)
            node_max_duration_url = get_job_url_by_duration(node_stats_type['duration'], node_max_duration_msec) + '/console'
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
        node_duration_output = '\t\tJob Run Duration Stats of Successful Job Runs (in mins): Max Duration = ' + cyan(node_max_duration) + ', Min Duration = ' + cyan(node_min_duration) + ', 50th-percentile = ' + cyan(node_duration_p50) + ', 75th-percentile = ' + cyan(node_duration_p75) + '\n'
        node_duration_output = node_duration_output + '\t\tConsole Output URL of Job Run with Max Duration (' + node_max_duration + ' mins): ' + node_max_duration_url + '\n'
        pnode_duration_output = '\t\tJob Run Duration Stats of Successful Job Runs (in mins): Max Duration = ' + str(node_max_duration) + ', Min Duration = ' + str(node_min_duration) + ', 50th-percentile = ' + str(node_duration_p50) + ', 75th-percentile = ' + str(node_duration_p75) + '\n'
        pnode_duration_output = pnode_duration_output + '\t\tConsole Output URL of Job Run with Max Duration (' + node_max_duration + ' mins:) ' + node_max_duration_url + '\n'
        hnode_duration_output = '\t\t<i>Job Run Duration Stats of Successful Job Runs (in mins):</i> Max Duration = ' + "<span style=\"color: red\">" + str(node_max_duration) + '</span>, Min Duration = ' + str(node_min_duration) + ', 50th-percentile = ' + "<span style=\"color: red\">" + str(node_duration_p50) + '</span>, 75th-percentile = ' + str(node_duration_p75) + '\n'
        hnode_duration_output = hnode_duration_output + '\t\t<i>Console Output URL of Job Run with Max Duration (' + "<span style=\"color: red\">" + node_max_duration + ' mins</span>:)</i> ' + "<a href=\"" + node_max_duration_url + "\">" + node_max_duration_url + "</a>" + '\n'
        ci_metrics_report = ci_metrics_report + node_duration_output
        ci_metrics_report_plain = ci_metrics_report_plain + pnode_duration_output
        ci_metrics_report_html = ci_metrics_report_html + hnode_duration_output
        
        # Timeline Output By Node
        ci_metrics_report = ci_metrics_report + node_hourly_output
        ci_metrics_report_plain = ci_metrics_report_plain + pnode_hourly_output
        ci_metrics_report_html = ci_metrics_report_html + pnode_hourly_output


    ci_metrics_report = ci_metrics_report + '*' * 150 + "\n"
    ci_metrics_report_plain = ci_metrics_report_plain + '*' * 150 + "\n"
    ci_metrics_report_html = ci_metrics_report_html + "</pre>" + "\n"
    ci_metrics_report_html = ci_metrics_report_html + html_footer()

    print(ci_metrics_report,end='')
    summary = open(jobs_summary_report_filename, 'w')
    summary.write(ci_metrics_report)
    summary.close()

    # Send the CI Metrics Report as Email
    send_ci_report_in_email(run_date, ci_metrics_report_plain, ci_metrics_report_html)


def send_ci_report_in_email(run_date, ci_metrics_report_plain, ci_metrics_report_html):
    email_user = "anasharm@cisco.com"
    email_pwd = "Fam1lyR0cks!"
    from_user = "anasharm@cisco.com"
    to_users = ", ".join(["anasharm@cisco.com", "anand.sharma@gmail.com"])
    subject = "CI Job Run Summary Report for " + run_date

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = from_user
    msg['To'] =  to_users

    # Create the body of the message (a plain-text and an HTML version)
    text = ci_metrics_report_plain
    html = ci_metrics_report_html

    part1 = MIMEText(text, 'plain')
    part2 = MIMEText(html, 'html')
    msg.attach(part1)
    msg.attach(part2)

    # Send the message via local SMTP server
    try:
        s = smtplib.SMTP('email.cisco.com', 587)
        s.ehlo()
        s.starttls()
        s.login(email_user, email_pwd)
        s.sendmail(from_user, to_users, msg.as_string())
        s.close()
        print("Successfully sent email with Subject:", subject)
    except:
        print("WARNING: Failed to send email with Subject:", subject)


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
    inside_modules = is_inside_modules(job_run) 
    if line_tokens[-3] == 'builds' and not inside_modules:
        job_run_basics_status = "SUCCESS"
        job_key = get_job_key(line_tokens[:-3])
        job_name = line_tokens[-4]
        job_date_tokens = line_tokens[-2].split('_')
        job_date = job_date_tokens[0]
        job_time_tokens = job_date_tokens[1].split('-')
        job_time_hr = job_time_tokens[0]
        job_time_min = job_time_tokens[1]
    return job_key, job_name, job_date, job_time_hr, job_time_min, job_run_basics_status


def is_inside_modules(job_run):
    inside_modules = False
    line_tokens = job_run.split('/')
    modules_folder_path = ''
    # print(job_run)
    if line_tokens[-5] == 'modules':
        modules_folder_path = '/'.join(line_tokens[:-5])
        modules_folder_path = modules_folder_path + '/builds'
        # print("I am in")
        if os.path.exists(modules_folder_path):
            # print("I am really inside")
            inside_modules = True
    # print('[' + modules_folder_path + ']')
    return inside_modules


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
