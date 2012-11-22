"""
Client to run the tests
"""
import json
import time
import yaml
import argparse
from thor import HttpClient
from thor import SpdyClient
from thor.loop import stop, run


def get_args():
    parser = argparse.ArgumentParser(
            description='Run HTTP and SPDY clients for test.')
    parser.add_argument('-c', '-config', type=str, required=True,
            dest='conf_file', action='store', help='YAML configuration file.')
    return parser.parse_args()


def hello(host):
    # TODO: Add id from server to all headers!
    resp = {'text': '', 'sitelist': []}

    def hello_start(status, phrase, headers):
        if status == '200':
            print 'Connection Successful!\nDownloading sitelist.'

    def hello_body(chunk):
        resp['text'] += chunk

    def hello_stop(trailers):
        resp['sitelist'] = json.loads(resp['text'])
        stop()

    httpclient = HttpClient()
    hello = httpclient.exchange()
    hello.on('response_start', hello_start)
    hello.on('response_body', hello_body)
    hello.on('response_done', hello_stop)
    uri = host + '/hello'
    hello.request_start('GET', uri, [])
    hello.request_done([])
    run()
    return resp['sitelist']


def collect(host, data):

    def collect_start(status, phrase, headers):
        print status, phrase, headers
        if status != '200':
            print 'Uploading data...'

    def collect_body(chunk):
        pass
        #print chunk

    def collect_stop(trailers):
        #print 'Finished!'
        stop()

    httpclient = HttpClient()
    collect = httpclient.exchange()
    collect.on('response_start', collect_start)
    collect.on('response_body', collect_body)
    collect.on('response_done', collect_stop)
    # TODO: Make this a POST
    collect.request_start('GET', host, [])
    collect.request_body(data)
    collect.request_done([])
    run()
    return "Upload Complete"


def http_siteget(http1, http2, site, httpclient):
    resp = {'text': '', 'assetlist': []}

    def site_start(status, phrase, headers):
        if status != '200':
            print 'Connection Failed: ' + site

    def site_body(chunk):
        resp['text'] += chunk

    def site_stop(trailers):
        resp['assetlist'] = json.loads(resp['text'])['list']
        stop()

    t0 = time.time()
    get = httpclient.exchange()
    get.on('response_start', site_start)
    get.on('response_body', site_body)
    get.on('response_done', site_stop)
    uri = http1 + '/site/' + str(site)
    get.request_start('GET', uri, [])
    get.request_done([])
    run()
    for asset in resp['assetlist']:
        # TODO: consider doing this with 4-6 connections?
        http_assetget(http1, http2, asset, httpclient)
    return time.time() - t0


def http_assetget(http1, http2, asset, httpclient):
    resp = {'text': ''}

    def asset_start(status, phrase, headers):
        if status != '200':
            print 'Connection Failed: ' + asset
            print status
            print phrase

    def asset_body(chunk):
        resp['text'] += chunk

    def asset_stop(trailers):
        stop()

    get = httpclient.exchange()
    get.on('response_start', asset_start)
    get.on('response_body', asset_body)
    get.on('response_done', asset_stop)
    parts = asset.split('/')
    if parts[0] == 'host1':
        uri = http1 + '/asset/' + parts[1]
    else:
        uri = http2 + '/asset/' + parts[1]
    get.request_start('GET', uri, [])
    get.request_done([])
    run()


def spdy_siteget(spdy1, spdy2, site):
    resp = {'text': '', 'assetlist': []}

    def site_start(status, phrase, headers):
        if status != '200':
            print 'Connection Failed: ' + site

    def site_body(chunk):
        resp['text'] += chunk

    def site_stop(trailers):
        resp['assetlist'] = json.loads(resp['text'])['list']
        stop()

    # FIXME: The spdy server is currently taking uri's differently than
    # the http server is. this should be fixed in thor
    t0 = time.time()
    spdyclient = SpdyClient()
    get = spdyclient.exchange()
    get.on('response_start', site_start)
    get.on('response_body', site_body)
    get.on('response_done', site_stop)
    uri = spdy1 + '/site/' + str(site)
    stream = get.request_start('GET', uri, [])
    get._streams[stream].request_done(stream, [])
    run()
    for asset in resp['assetlist']:
        spdy_assetget(spdy1, spdy2, asset)
    return time.time() - t0


def spdy_assetget(spdy1, spdy2, asset):
    resp = {'text': ''}

    def asset_start(status, phrase, headers):
        if status != '200':
            print 'Connection Failed: ' + asset
            print status
            print phrase

    def asset_body(chunk):
        resp['text'] += chunk

    def asset_stop(trailers):
        stop()

    spdyclient = SpdyClient()
    get = spdyclient.exchange()
    get.on('response_start', asset_start)
    get.on('response_body', asset_body)
    get.on('response_done', asset_stop)
    parts = asset.split('/')
    if parts[0] == 'host1':
        uri = spdy1 + '/asset/' + parts[1]
    else:
        uri = spdy2 + '/asset/' + parts[1]
    stream = get.request_start('GET', uri, [])
    get._streams[stream].request_done(stream, [])
    run()


def main():
    args = get_args()
    conf = yaml.load(file(args.conf_file, 'r'))

    mainhost_http = conf['mainhost'] + ':' + str(conf['http_port'])
    mainhost_spdy = conf['mainhost'] + ':' + str(conf['spdy_port'])
    secondhost_http = conf['secondhost'] + ':' + str(conf['http_port'])
    secondhost_spdy = conf['secondhost'] + ':' + str(conf['spdy_port'])
    mainhost_collect = conf['mainhost'] + ':' + str(conf['capture_port'])

    times = {}
    sites = hello(mainhost_http)
    httpclient = HttpClient()
    for i,site in enumerate(sites):
        print i
        http_delta = http_siteget(mainhost_http,
                secondhost_http,
                site,
                httpclient)
        #spdy_siteget(mainhost_spdy,
        #        secondhost_spdy,
        #        site)
        times[site] = {}
        times[site]['http'] = http_delta
        #times[site]['spdy'] = spdy_delta

    print 'Testing complete!'
    result = collect(mainhost_collect, json.dumps(times))
    print result
    stop()

# FIXME: This might not be reusing connections for SPDY!  Fix that.


if __name__ == '__main__':
    main()
