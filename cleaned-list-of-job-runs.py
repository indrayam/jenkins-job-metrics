from __future__ import print_function
import re

filename = './config-samples/output.txt'

all_count = 0
lines_with_modules_count = 0
lines_without_modules_count = 0
lines_with_success_count = 0
with open(filename, 'r') as file:
    for line in file.readlines():
        line = line.strip()
        all_count = all_count + 1
        if re.match(r'.*:modules.*', line, re.I):
            lines_with_modules_count = lines_with_modules_count + 1
            continue
        else:
            lines_without_modules_count = lines_without_modules_count + 1
            line_tokens = line.split('|')
            if line_tokens[-1] == 'SUCCESS':
                lines_with_success_count = lines_with_success_count + 1

print('Number of Jobs TOTAL:', all_count)
print('Number of Jobs without Modules:', lines_without_modules_count)
print('Number of Jobs with Modules:', lines_with_modules_count)
print('Number of Jobs with SUCCESS:', lines_with_success_count)


