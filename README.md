# Toggl to Beeminder

## Features

This is a toggl to beeminder integration. It will automatically update your beeminder goals when you add time entries in toggl corresponding to them.

- All time entries that you want synchronized to a given beeminder goal should be part of a single toggl project. The names of the goal and the project may be different.

- If you change a time entry in toggl (changing the amount of time, changing the project etc.) within 24 hours of creating it, the changes will be reflected in beeminder.

## Install

This project requires python. No libraries should be necessary: the only non-standard library used is tendo.singleton, but I included it in the repo.

These installation steps should work for Mac OS X, Linux, or any other Unix system with python. For Windows, you will need to find a way to run the python script repeatedly.

### Configuration

First, you need to create a config file:

`cp data/toggl.cfg.example data/toggl.cfg`

Then edit toggl.cfg. The first part involves setting which toggl projects correspond to which beeminder goals. You need to enumerate all projects and goals here even if they have the same name!!!

For example, if your toggl project is called "Be Productive" and your beeminder goal is called "prod", the "project_to_goal" section should contain `"be productive": "prod"`. If you aren't familiar with the JSON format, please note that you should separate different "project": "goal" items with commas, but that the last item shouldn't be followed by a comma.

Also note that the beeminder goals should NOT be the user friendly goal names but should be the goal URL name. For example, if your goal is called "Be More Productive", but when you navigate to it you see `https://www.beeminder.com/<your_username>/goals/prod` in your browser's URL bar, you should use "prod" as your goal name here.

Then in the goal_to_time_unit section, include the unit of your various beeminder goals. For instance, if your "prod" goal is measured in seconds, you should have `"prod": "s"`. Supported units include "s" (seconds), "m" (minutes), "h" (hours) and "d" (days).

Your beeminder_token can be found at https://www.beeminder.com/settings/advanced_settings

Your toggl_token can be found at https://www.toggl.com/app/profile

Your beeminder user name is whatever you use to log into beeminder (obviously). Write it in lowercase.

### Initializing

The very first thing you absolutely need to do is run the script once.

`python sync_toggl.py`.

Any toogl entry that you created prior to running the script for the first time will be ignored. Every toggl entry that you subsequently create will be synchronized to beeminder.

### Making the script run repeatedly

Add your script as a cron by using (in shell):

`EDITOR=nano crontab -e`

This will open an editor with a cron configuration file. Add the following line in the file:

`* * * * * python <PATH_TO_THE_SCRIPT>/sync_toggl.py`

Of course, replace <PATH_TO_THE_SCRIPT> with the path to the directory that contains sync_toggl.py (For example: `/User/yourname/beeminder_toggl/`).

Then save and exit.

You're all set. The script will run every minute, which means that every new entry in toggl will be reflected in beeminder within a minute.
