CLC SSH Config Builder
==============
This script will scan through all listed CenturyLink Cloud Aliases that you specify and generate an SSH config file to allow for easier server access. It is recommended that you configure this script and then set it in cron to run at a regularly scheduled interval.

Variables to specify:
--------------
- CLC_API_V2_USERNAME: Your CenturyLink Cloud Username
- CLC_API_V2_PASSWD: Your CenturyLink Cloud Password
- CLC_ALIASES: The accont aliases that you want to use to generate the config (*['alias1', 'alias2']*)
- SSH_DIR: Where you want your SSH config file to be placed (*/home/user/.ssh*)
