import json

import sys
import os
import yaml
from kazoo.client import KazooClient


def set_value(zookeeper, path, value):
    zookeeper.ensure_path(path)
    value = bytes('{0}'.format(value), 'utf-8')
    if zookeeper.get(path)[0] != value:
        print('set {0} = {1}'.format(path, value))
        zookeeper.set(path, value)


def push_file(zookeeper, angler_id):
    file = open('{0}.yaml'.format(angler_id))
    angler = yaml.load(file)
    file.close()
    angler_path = 'angler/{0}'.format(angler['id'])
    set_value(zookeeper, angler_path, angler['name'])
    for container_name in angler['containers'].keys():
        container_path = angler_path + '/containers/{0}'.format(container_name)
        container = angler['containers'][container_name]
        events = container['events']
        del container['events']
        set_value(zookeeper, container_path, json.dumps(container))

        events_path = container_path + '/events'
        for old_event in zookeeper.get_children(events_path):
            if old_event not in events.keys():
                zookeeper.delete('{0}/{1}'.format(events_path, old_event))
                print('del {0}/{1}'.format(events_path, old_event))

        for event_name in events.keys():
            event = events[event_name]
            if event.get('package') is None:
                file = open('./{0}/{1}.py'.format(angler_id, event_name))
                event['script'] = file.read()
            set_value(zookeeper, '{0}/{1}'.format(events_path, event_name), json.dumps(event))

    services_path = angler_path + '/services'
    for old_service in zookeeper.get_children(services_path):
        if old_service not in angler['services'].keys():
            zookeeper.delete('{0}/{1}'.format(services_path, old_service))
            print('del {0}/{1}'.format(services_path, old_service))

    for service_name in angler['services'].keys():
        set_value(zookeeper, '{0}/{1}'.format(services_path, service_name), json.dumps(angler['services'][service_name]))
    print('push {0} finish'.format(angler_id))


def pull_file(zookeeper, angler_id):
    path = './{0}'.format(angler_id)
    if not os.path.isdir(path):
        os.mkdir(path)

    angler = dict()
    angler['id'] = angler_id
    angler_path = '/angler/{0}'.format(angler_id)

    if not zookeeper.exists(angler_path):
        print('not found {0} node'.format(angler_id))
        return
    angler['name'] = zookeeper.get(angler_path)[0].decode('utf-8')
    containers = dict()
    angler['containers'] = containers
    for container_name in zookeeper.get_children(angler_path + '/containers'):
        containers[container_name] = json.loads(
            zookeeper.get(angler_path + '/containers/{0}'.format(container_name))[0].decode('utf-8'))
        container = containers[container_name]
        container['events'] = dict()
        for event_name in zookeeper.get_children(angler_path + '/containers/{0}/events/'.format(container_name)):
            event = json.loads(
                zookeeper.get(angler_path + '/containers/{0}/events/{1}'.format(container_name, event_name))[0].decode('utf-8'))
            script = event.get('script')
            if script is not None:
                file = open('./{0}/{1}.py'.format(angler_id, event_name), 'w')
                file.write(script)
                file.close()
                del event['script']
            container['events'][event_name] = event

    services = dict()
    angler['services'] = services
    for service_name in zookeeper.get_children(angler_path + '/services'):
        services[service_name] = json.loads(zookeeper.get(angler_path + '/services/{0}'.format(service_name))[0].decode('utf-8'))

    file = open('{0}.yaml'.format(angler_id), 'w')
    yaml.dump(angler, file, default_flow_style=False)
    file.close()
    print('pull {0} finish'.format(angler_id))


def main(argv):
    if len(argv) != 3:
        return
    if argv[1] not in ['push', 'pull']:
        return

    file = open('angler_zookeeper.yaml')
    conf = yaml.load(file)
    file.close()
    zookeeper = KazooClient(conf['zookeeper']['hosts'])
    zookeeper.start()
    if argv[1] == 'push':
        push_file(zookeeper, argv[2])
    elif argv[1] == 'pull':
        pull_file(zookeeper, argv[2])

if __name__ == "__main__":
    main(sys.argv)
