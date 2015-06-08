import base64
from datetime import datetime, timedelta
import httplib
import json
import os
import signal
import singleton
import sys
import urllib2
import urllib

me = singleton.SingleInstance() # will sys.exit(-1) if other instance is running

base_dir = os.path.dirname(os.path.realpath(__file__))


# Never let this run for more than 5 minutes
signal.alarm(5 * 60)

config_file = base_dir + '/data/toggl.cfg'
store_file = base_dir + '/data/time_entries'

config = json.loads(open(config_file).read())

def beeminder_add_entry(project, time, comment=''):
    """Add an entry of a given value to a given project in beeminder."""
    url = '/users/%s/goals/%s/datapoints.json?auth_token=%s&value=%s&comment=%s' % (
        config['beeminder_user'],
        project,
        config['beeminder_token'],
        time,
        '+'.join(comment.split())
    )
    gethttp(url, data ='', method='POST', api='beeminder')

token = config['toggl_token']

def gethttp(url, data=None, method='GET', api='toggl'):
    """Call either the beeminder or the toggl API.

    Note: this handles using fancy http methods which as it turns out isn't necessary for
    this particular script.

    """
    # Choose the right API based on the url
    if api == 'toggl':
        real_url = 'https://www.toggl.com/api/v8/' + url
    elif api == 'beeminder':
        real_url = 'https://www.beeminder.com/api/v1/' + url
    else:
        real_url = url

    request = urllib2.Request(real_url, data=data, headers={'Content-type': 'application/json'})

    ##########################################################################################
    # HACK: We need to handle authorization using tokens and using PUT and DELETE requests   #
    #       with urllib. This requires this pretty hacky code.                               #
    ##########################################################################################
    base64string = base64.encodestring('%s:%s' % (token, 'api_token')).replace('\n', '')
    request.add_header("Authorization", "Basic %s" % base64string)
    request.get_method = lambda: method
    class PutRedirectHandler(urllib2.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            """Return a Request or None in response to a redirect.
            This is called by the http_error_30x methods when a
            redirection response is received.  If a redirection should
            take place, return a new Request to allow http_error_30x to
            perform the redirect.  Otherwise, raise HTTPError if no-one
            else should try to handle this url.  Return None if you can't
            but another Handler might.
            """
            # This is a modified version of the parent implementation that also handles PUT and DELETE
            m = req.get_method()
            if (code in (301, 302, 303, 307) and m in ("GET", "HEAD")
                or code in (301, 302, 303) and m in ("POST", "PUT", "DELETE")):
                # Strictly (according to RFC 2616), 301 or 302 in response
                # to a POST MUST NOT cause a redirection without confirmation
                # from the user (of urllib2, in this case).  In practice,
                # essentially all clients do redirect in this case, so we
                # do the same.
                # be conciliant with URIs containing a space
                newurl = newurl.replace(' ', '%20')
                newheaders = dict((k,v) for k,v in req.headers.items()
                                  if k.lower() not in ("content-length", "content-type")
                                 )
                print newurl
                return urllib2.Request(newurl,
                               headers=newheaders,
                               origin_req_host=req.get_origin_req_host(),
                               unverifiable=True)
            else:
                raise urllib2.HTTPError(req.get_full_url(), code, msg, headers, fp)
    ##########################################################################################
    # End of hack                                                                            #
    ##########################################################################################

    opener = urllib2.build_opener(PutRedirectHandler)

    try:
        return json.loads(opener.open(request).read())
    except Exception, e:
        print e.read()

# First get all the projects in toggle. For that, we need to get all the workspaces.
workspaces = gethttp('workspaces')

# Get the corresponding ids to names of projects. Note: you might have two different
# projects with the same name in toggle. DO NOT DO THAT HERE. This program will fail
# if you do.
id_to_project_name = {}
for workspace in workspaces:
    projects = gethttp('workspaces/%s/projects' % workspace['id'])
    for project in projects:
        assert project['name'] not in id_to_project_name
        id_to_project_name[project['id']] = project['name'].lower()

def pastisotime(n_previous_days):
    """Get the current timestamp minus a certain number of days in ISO utc time."""
    time = datetime.utcnow() - timedelta(days=n_previous_days)
    time = time.isoformat()
    return time.split('.')[0] + '+00:00'

# All entries in the past day. Feel free to increase that number of days if you want
# to look back further.
past_time = pastisotime(1)
entries = gethttp('time_entries?%s' % urllib.urlencode({'start_date': past_time}))


def decide(entry):
    """Decide what beeminder project to assign to a certain entry.

    Some special cases:
    - no projects will be assigned if the entry is currently running
    - the special project '__none__' will be returned if no beeminder project is assigned.

    """
    pid = entry.get('pid')
    # stop is none if entry isn't finished yet.
    if pid is None or entry.get('stop') is None:
        return '__none__'
    project = id_to_project_name[pid]
    return config['project_to_goal'].get(project, '__none__')

def get_time(entry):
    """Return the elapsed time for a given entry where a decision was taken.

    Converts to the time unit of the beeminder project. Default unit: minute.

    """
    decision = entry['decision']
    time_type = config['goal_to_time_unit'].get(decision, 'm')
    if time_type == 's':
        return entry['duration']
    if time_type == 'm':
        return entry['duration'] / 60.0
    if time_type == 'h':
        return entry['duration'] / (60.0*60.0)

# We will set download_only to True if it appears that this script has never been run
# previously on this computer, in which case any time entry that we find will be ignored,
# and only subsequent time entries will be used.
download_only = False
try:
    data = open(store_file).read()
    json.loads(data)
except Exception:
    download_only = True

# Note: technically using a TODO isn't strictly necessary in hindsight, the actions could be
# performed right away.
todo = []

entries_by_ids = {str(entry['id']): entry for entry in entries}

if download_only:
    # Ignore all the decisions that we found. The special value '__ignore__' means that
    # the entry will be ignored forever, wherease '__none__' means that the entry was
    # ignored but can be reconsidered in the future.
    for entry in entries:
        entry['decision'] = '__ignore__'
else:
    # We get the old entries to not re-record a beeminder entry that we already
    # recorded.
    old_entries = json.loads(data)
    for entry in entries:
        entry['decision'] = decide(entry)
        # We need to use string ids everywhere because JSON doesn't support int ids
        strid = str(entry['id'])
        if strid not in old_entries:
            # First time we see this entry, add it to beeminder
            todo.append(('do', entry, 'From toggl_beeminder'))
        elif ((entry['decision'] != old_entries[strid]['decision']
               or entry['duration'] != old_entries[strid]['duration'])):
            # We've seen this entry before, but it has either changed projects or duration
            # since.
            if old_entries[strid]['decision'] == '__ignore__':
                # If the original decision was to ignore, we need to ignore this guy too.
                entry['decision'] = '__ignore__'
            else:
                # Otherwise, change the value by cancelling the previous entry and creating it again
                # with the right time in the right project.
                todo.append(('cancel', old_entries[strid], 'Project or time changed in toggl (from toogl_beeminder)'))
                todo.append(('do', entry, 'From toggl_beeminder'))
            # Remove the old entry because it is accounted for
            del old_entries[strid]
        else:
            # Remove the old entry because it is accounted for
            del old_entries[strid]

    for bad_old in old_entries.values():
        # For the remaining (unaccounted for) old entries, there are two possible cases:
        # 1/ They disappeared because they started before the look-back time, which is normal.
        # 2/ They disappeared because they were removed in toggl, in which case we remove them
        #    from beeminder.
        if bad_old['start'] < past_time:
            continue # The entry disappeared because we moved forward in time
        todo.append(('cancel', bad_old, 'Time entry deleted from Toggl'))

    # Apply the decisions for all the entries.
    for action, entry, comment in todo:
        if entry['decision'] in ('__ignore__', '__none__'):
            continue
        if action == 'do':
            beeminder_add_entry(entry['decision'], get_time(entry), comment)
        elif action == 'cancel':
            beeminder_add_entry(entry['decision'], -get_time(entry), comment)
        else:
            unknownactionerror

# Save the current set of entry.
json.dump(entries_by_ids, open(store_file, 'w+'), indent=2)
