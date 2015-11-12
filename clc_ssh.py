import sys
import os
from multiprocessing import Pool
import itertools
import json
import clc
from clc import CLCException, APIFailedResponse

CLC_API_V2_USERNAME = ""
CLC_API_V2_PASSWD = ""
#CLC_ALIASES = ['wfaq', 'wfaq', 'wfts', 'rnrp', 'wfas', 'wfad']
CLC_ALIASES = ['wfaq', 'wfad']
HOSTVAR_POOL_CNT = 25

def main():
    print_ssh_config()
    sys.exit(0)

def print_ssh_config():
    _set_clc_credentials()
    for alias in CLC_ALIASES:
        clc.ALIAS = alias

        groups = _find_all_groups()
        servers = _get_servers_from_groups(groups)
        hostvars = _find_all_hostvars_for_servers(servers)

        result = groups
        result['_meta'] = hostvars

        for server in hostvars:
            print server
            print hostvars[server]['ipAddress']

#    print(json.dumps(hostvars, indent=2, sort_keys=True))

def _find_all_groups():
    '''
    Obtain a list of all datacenters for the account, and then return a list of their Server Groups
    :return: group dictionary
    '''
    datacenters = _filter_datacenters(clc.v2.Datacenter.Datacenters())
    results = [_find_groups_for_datacenter(datacenter) for datacenter in datacenters]

    # Filter out results with no values
    results = [result for result in results if result]
    return _parse_groups_result_to_dict(results)

def _filter_datacenters(datacenters):
    '''
    Return only datacenters that are listed in the CLC_FILTER_DATACENTERS env var
    :param datacenters: a list of datacenters to filter
    :return: a filtered list of datacenters
    '''
    include_datacenters = os.environ.get('CLC_FILTER_DATACENTERS')
    if include_datacenters:
        return [datacenter for datacenter in datacenters if str(
            datacenter).upper() in include_datacenters.upper().split(',')]
    else:
        return datacenters


def _find_groups_for_datacenter(datacenter):
    '''
    Return a dictionary of groups and hosts for the given datacenter
    :param datacenter: The datacenter to use for finding groups
    :return: dictionary of { '<GROUP NAME>': 'hosts': [SERVERS]}
    '''
    result = {}
    groups = datacenter.Groups().groups
    result = _find_all_servers_for_group( datacenter, groups )
    if result:
        return result

def _find_all_servers_for_group( datacenter, groups):
    '''
    recursively walk down all groups retrieving server information.
    :param datacenter: The datacenter being search.
    :param groups: The current group level which is being searched.
    :return: dictionary of {'<GROUP NAME>': 'hosts': [SERVERS]}
    '''
    result = {}
    for group in groups:
        sub_groups = group.Subgroups().groups
        if ( len(sub_groups) > 0 ):
            sub_result = {}
            sub_result = _find_all_servers_for_group( datacenter, sub_groups )
            if sub_result is not None:
                result.update( sub_result )

        if group.type != 'default':
            continue

        try:
            servers = group.Servers().servers_lst
        except CLCException:
            continue  # Skip any groups we can't read.

        if servers:
            result[group.name] = {'hosts': servers}
            result[
                str(datacenter).upper() +
                '_' +
                group.name] = {
                'hosts': servers}

    if result:
        return result


def _find_all_hostvars_for_servers(servers):
    '''
    Return a hostvars dictionary for the provided list of servers.
    Multithreaded to optimize network calls.
    :cvar HOSTVAR_POOL_CNT: The number of threads to use
    :param servers: list of servers to find hostvars for
    :return: dictionary of servers(k) and hostvars(v)
    '''
    p = Pool(HOSTVAR_POOL_CNT)
    results = p.map(_find_hostvars_single_server, servers)
    p.close()
    p.join()

    hostvars = {}
    for result in results:
        if result is not None:
            hostvars.update(result)

    return hostvars


def _find_hostvars_single_server(server_id):
    '''
    Return dictionary of hostvars for a single server
    :param server_id: the id of the server to query
    :return:
    '''
    result = {}
    try:
        session = clc.requests.Session()

        server_obj = clc.v2.API.Call(method='GET',
                                     url='servers/{0}/{1}'.format(clc.ALIAS, server_id),
                                     payload={},
                                     session=session)

        server = clc.v2.Server(id=server_id, server_obj=server_obj)

        if len(server.data['details']['ipAddresses']) == 0:
            return

        result[server.name] = {
            'ipAddress': server.data['details']['ipAddresses'][0]['internal'],
            'clc_data': server.data
        }
    except (CLCException, APIFailedResponse, KeyError):
        return  # Skip any servers that return bad data or an api exception

    return result


def _parse_groups_result_to_dict(lst):
    '''
    Return a parsed list of groups that can be converted to Ansible Inventory JSON
    :param lst: list of group results to parse
    :return: dictionary of groups and hosts { '<GROUP NAME>': 'hosts': [SERVERS]}
    '''
    result = {}
    for groups in sorted(lst):
        for group in groups:
            if group not in result:
                result[group] = {'hosts': []}
            result[group]['hosts'] += _flatten_list(groups[group]['hosts'])
    return result


def _get_servers_from_groups(groups):
    '''
    Return a flat list of servers for the provided dictionary of groups
    :param groups: dictionary of groups to parse
    :return: flat list of servers ['SERVER1','SERVER2', etc]
    '''
    return set(_flatten_list([groups[group]['hosts'] for group in groups]))


def _flatten_list(lst):
    '''
    Flattens a list of lists until at least one value is no longer iterable
    :param lst: list to flatten
    :return: flattened list
    '''
    while not _is_list_flat(lst):
        lst = list(itertools.chain.from_iterable(lst))
    return lst


def _is_list_flat(lst):
    '''
    Checks to see if the list contains any values that are not iterable.
    :param lst: list to check
    :return: True if any value in the list is not an iterable
    '''
    result = True if len(lst) == 0 else False
    i = 0
    while i < len(lst) and not result:
        result |= (
            not isinstance(lst[i], list) and
            not isinstance(lst[i], dict) and
            not isinstance(lst[i], tuple) and
            not isinstance(lst[i], file))
        i += 1
    return result

def _set_clc_credentials():
    env = os.environ
    v2_api_token = env.get('CLC_V2_API_Token', False)
    v2_api_username = CLC_API_V2_USERNAME
    v2_api_passwd = CLC_API_V2_PASSWD

    if v2_api_token and clc_alias:
        clc._LOGIN_TOKEN_V2 = v2_api_token
        clc._V2_ENABLED = True
    elif v2_api_username and v2_api_passwd:
        clc.v2.SetCredentials(api_username=v2_api_username,
                              api_passwd=v2_api_passwd)

if __name__ == '__main__':
    main()
