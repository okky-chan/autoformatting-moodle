from utils import *

import re
from sys import argv


QUIET = "-q" in argv[1:]
SKIP_CORPORATE_ENTRE = "-skip-corpo-entre" in argv[1:]
SKIP_START_UP = "-skip-start-up" in argv[1:]

if not QUIET:
    print('Active flags: ' + repr({
        'QUIET': QUIET,
        'SKIP_CORPORATE_ENTRE': SKIP_CORPORATE_ENTRE,
        'SKIP_START_UP': SKIP_START_UP
    }))

unregistered = []
courses = {}
teaching_lecturers = {}
enrolments = []

new_user_mapping = {}
course_lecturer_mapping = {}

statepro_courses = {}
statepro_map = {}

session_morning = []
session_night = []


ex_entre = re.compile(r'^Entrepreneurship [0-9]+')
ex_corpo_entre = re.compile(r'^Corporate Entrepreneurship [0-9]+')

# --
with open('courses.csv', newline='') as csvfile:
    reader = csv.reader(csvfile, delimiter=',', quotechar='"')
    for row in reader:
        #fullname,Class Name,shortname,category_idnumber,enrolment_1,enrolment_1_role,enrolment_1_password

        fullname = row[0]
        classname = row[1]
        shortname = row[2]
        category_idnumber = row[3]

        session_cat = category_idnumber[6]  # M or N

        if fullname == 'fullname' or fullname == 'Course Full Name':
            continue

        if fullname in ("Pancasila", "Religion", "Indonesian Language"):
            # skip duplicate statepro
            statepro_map[shortname] = "Statepersonship Project ({})".format(classname)
            continue

        if fullname == "Citizenship":
            real_shortname = shortname
            fullname = "Statepersonship Project ({})".format(classname)
            shortname = "{}_StatePro".format(shortname[:5])
            category_idnumber = "{}STATEPRO".format(category_idnumber[:6])
        elif fullname == 'Start-Up2' and SKIP_START_UP:
            if not QUIET:
                print(f'Skipping course: {repr(shortname)}')
            continue
        elif fullname[:7] == 'English':
            real_shortname = None
            fullname = "{} ({})".format(fullname, classname)
            category_idnumber = "{}ENGLISH".format(category_idnumber[:6])
        elif ex_entre.match(fullname) is not None or ex_corpo_entre.match(fullname) is not None:
            # Skip Corporate Entrepreneurship, special case for now. Remove when not needed.
            #if fullname[:28] == "Corporate Entrepreneurship 1" and SKIP_CORPORATE_ENTRE:
            if fullname[:26] == "Corporate Entrepreneurship" and SKIP_CORPORATE_ENTRE:
                if not QUIET:
                    print(f'Skipping course: {repr(shortname)}')
                continue

            real_shortname = None
            fullname = "{} ({})".format(fullname, classname)
            category_idnumber = "{}ENTREPRENEURSHIP".format(category_idnumber[:6])
        else:
            real_shortname = None
            fullname = "{} ({})".format(fullname, classname)
            category_idnumber = translate_category(category_idnumber)

        enrolment_1_password = f"{int(row[6]):04d}"

        # PUIS generated idnumber
        idnumber = get_course_idnumber(shortname)
        if idnumber is None:
            print("FAIL to get idnumber for {}".format(shortname))
            exit(0)

        courseinfo = {
            "fullname": fullname,
            "shortname": shortname,
            "idnumber": idnumber,
            "category_idnumber": category_idnumber,
            "enrolment_1": 'self',
            "enrolment_1_role": 'student',
            "enrolment_1_password": enrolment_1_password,
            "startdate": COURSE_STARTDATE,
            "enddate": COURSE_ENDDATE,
            "format": "remuiformat",
            "visible": "1"
        }

        if session_cat == 'M':
            session_morning.append(courseinfo)
        elif session_cat == 'N':
            session_night.append(courseinfo)
        else:
            print(f"FAIL invalid session cat {session_cat} for idnumber {idnumber}")
            exit(0)

        if real_shortname:
            statepro_courses[fullname] = courseinfo
            statepro_map[real_shortname] = "Statepersonship Project ({})".format(classname)

        courses[shortname] = courseinfo


with open('lecturers.csv', newline='') as csvfile:
    reader = csv.reader(csvfile, delimiter=',', quotechar='"')
    for row in reader:
        # email,fullname,shortname,role1

        emails = [translate_email(i) for i in row[0].split(', ')]
        fullname = row[1]
        shortname = row[2]

        if emails[0] == 'email' or emails[0] == 'Lecturer Email(s)':
            continue

        if len(fullname) == 0 or fullname == "(Tba)" or len(emails) < 1 or len(emails[0]) == 0:
            if not QUIET:
                print("Skipping row: empty name and email for %s." % shortname)
            continue

        cn = shortname[6:]

        """
        if shortname in skipped:
            continue
        """

        email = prefer_internal_email(emails)

        found, lec = find_in_lecturers(emails)
        if found is False:
            firstname, lastname = generate_firstname_lastname(fullname)
            username = generate_username(firstname, lastname)

            print("REG: {} ({})".format(fullname, ', '.join(emails)))

            unregistered.append({
                'firstname': firstname,
                'lastname': lastname,
                'username': username,
                'email': email,
                'password': email,
                'profile_field_puis_bridge_user_type': 'lecturer'
            })

            lec = {
                'username': username,
                'email': email,
                'firstname': firstname,
                'lastname': lastname
            }

            lecturers.append(lec)
            lecturers_by_email[email] = lec
            new_user_mapping[email] = True
        else:
            username = lec['username']
            firstname = lec['firstname']
            lastname = lec['lastname']

        if lec['username'] not in teaching_lecturers:
            teaching_lecturers[lec['username']] = lec

        if shortname in statepro_map:
            course = statepro_courses[statepro_map[shortname]]
        elif shortname in courses:
            course = courses[shortname]
        else:
            continue

        course_shortname = course["shortname"]

        enrolments.append({
            'username': username,
            'course1': course_shortname,
            'role1': 'editingteacher',
            'enrolstatus1': '0',
            'cohort1': CATEGORY_PREFIX + 'LECTURERS',
            'cohort2': CATEGORY_PREFIX + 'LECTURERS_' + get_course_abbreviation(course['category_idnumber']),
            'profile_field_puis_bridge_user_type': 'lecturer'
        })

        if course_shortname not in course_lecturer_mapping:
            course_lecturer_mapping[course_shortname] = []

        course_lecturer_mapping[course_shortname].append(lec)


recap_morning = []
recap_night = []

# Create recap for Morning
for c in session_morning:
    c_fullname = c['fullname']
    c_shortname = c["shortname"]
    c_idnumber = c['idnumber']
    c_category_idnumber = get_course_category(c['category_idnumber'])
    c_enrolment_1_password = c['enrolment_1_password']

    if c_shortname in course_lecturer_mapping:
        users = course_lecturer_mapping[c_shortname]
        for u in users:
            u_email = u['email']

            recap_morning.append({
                'firstname': u["firstname"],
                'lastname': u["lastname"],
                'username': u["username"],
                'email': u_email,
                'category': c_category_idnumber,
                'course': c_fullname,
                'course_idnumber': c_idnumber,
                'enrolment_password': c_enrolment_1_password,
                'is_new_user': str(u_email in new_user_mapping),
            })
    else:
        recap_morning.append({
            'firstname': '',
            'lastname': '',
            'username': '(Tba)',
            'email': '',
            'category': c_category_idnumber,
            'course': c_fullname,
            'course_idnumber': c_idnumber,
            'enrolment_password': c_enrolment_1_password,
            'is_new_user': True,
        })

# Create recap for Night
for c in session_night:
    c_fullname = c['fullname']
    c_shortname = c["shortname"]
    c_idnumber = c['idnumber']
    c_category_idnumber = get_course_category(c['category_idnumber'])
    c_enrolment_1_password = c['enrolment_1_password']

    if c_shortname in course_lecturer_mapping:
        users = course_lecturer_mapping[c_shortname]
        for u in users:
            u_email = u['email']

            recap_night.append({
                'firstname': u["firstname"],
                'lastname': u["lastname"],
                'username': u["username"],
                'email': u_email,
                'category': c_category_idnumber,
                'course': c_fullname,
                'course_idnumber': c_idnumber,
                'enrolment_password': c_enrolment_1_password,
                'is_new_user': str(u_email in new_user_mapping),
            })
    else:
        recap_night.append({
            'firstname': '',
            'lastname': '',
            'username': '(Tba)',
            'email': '',
            'category': c_category_idnumber,
            'course': c_fullname,
            'course_idnumber': c_idnumber,
            'enrolment_password': c_enrolment_1_password,
            'is_new_user': True,
        })

# Create recap for all
recap_all = recap_morning + recap_night


# --
print("... Generating CSV ...")
print("=> Course count:", len(courses))
print("=> Lecturer count:", len(teaching_lecturers))

write_to_csv(
    'generated_courses_create.csv',
    ['fullname', 'shortname', 'idnumber', 'category_idnumber', 'enrolment_1', 'enrolment_1_role', 'enrolment_1_password', 'startdate', 'enddate', 'format', 'visible'],
    list(courses.values())
)

write_to_csv(
    'generated_lecturers_create.csv',
    ['firstname', 'lastname', 'username', 'email', 'password', 'profile_field_puis_bridge_user_type'],
    unregistered
)

write_to_csv(
    'generated_enrolments.csv',
    ['username', 'course1', 'role1', 'enrolstatus1', 'cohort1', 'cohort2', 'profile_field_puis_bridge_user_type'],
    enrolments
)

write_to_csv(
    'generated_recap_all.csv',
    ['firstname', 'lastname', 'username', 'email', 'category', 'course', 'enrolment_password', 'course_idnumber', 'is_new_user'],
    recap_all
)

write_to_csv(
    'generated_recap_morning.csv',
    ['firstname', 'lastname', 'username', 'email', 'category', 'course', 'enrolment_password', 'course_idnumber', 'is_new_user'],
    recap_morning
)

write_to_csv(
    'generated_recap_night.csv',
    ['firstname', 'lastname', 'username', 'email', 'category', 'course', 'enrolment_password', 'course_idnumber', 'is_new_user'],
    recap_night
)

write_to_csv(
    'generated_statepro_mapping.csv',
    ['real_shortname', 'changed_to'],
    [{'real_shortname': k, 'changed_to': statepro_courses[v]["shortname"]} for k, v in statepro_map.items()]
)
