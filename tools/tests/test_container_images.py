"""Synthetic content-addressed archives; no daemon, network or customer data."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile

import pytest

spec = importlib.util.spec_from_file_location('container_images', Path(__file__).parents[1] / 'handover/container_images.py')
images = importlib.util.module_from_spec(spec)
spec.loader.exec_module(images)


@pytest.fixture
def bundle(tmp_path):
    blobs = {}

    def add(data):
        raw = data if isinstance(data, bytes) else json.dumps(data).encode()
        digest = hashlib.sha256(raw).hexdigest()
        blobs['blobs/sha256/' + digest] = raw
        return {'digest':'sha256:' + digest, 'size':len(raw)}

    layer = add(b'synthetic layer')
    second = add(b'synthetic second layer')
    diff = 'sha256:' + hashlib.sha256(b'synthetic unpacked layer').hexdigest()
    diff2 = 'sha256:' + hashlib.sha256(b'synthetic second unpacked layer').hexdigest()
    config = add({'os':'linux','architecture':'amd64','rootfs':{'type':'layers','diff_ids':[diff,diff2]}})
    manifest = add({'config':config,'layers':[layer,second]})
    root = add({'manifests':[{**manifest,'platform':{'os':'linux','architecture':'amd64'}}]})
    tag = 'eims-transfer/synthetic:verified'
    blobs['index.json'] = json.dumps({'manifests':[{**root,'annotations':{'io.containerd.image.name':'docker.io/' + tag}}]}).encode()
    blobs['manifest.json'] = json.dumps([{'RepoTags':[tag], 'Config':'blobs/sha256/' + config['digest'][7:],
        'Layers':['blobs/sha256/' + d['digest'][7:] for d in (layer,second)]}]).encode()
    path = tmp_path / 'images.tar'

    def write():
        with tarfile.open(path, 'w') as tar:
            for name, raw in blobs.items():
                member = tarfile.TarInfo(name); member.size = len(raw)
                tar.addfile(member, io.BytesIO(raw))

    write()
    records = [{'tag':tag,'imageId':root['digest']}]
    record = images.archive_identities(path, records)[0]
    return path, records, record, blobs, write


@pytest.mark.parametrize('role', ['indexDigest','manifestDigest','configDigest'])
def test_accepts_only_archive_bound_identity_and_exact_layers(bundle, role):
    _, _, record, _, _ = bundle
    v = record['verification']
    actual = {'Id':v[role],'Os':'linux','Architecture':'amd64','RootFS':{'Type':'layers','Layers':v['diffIds']}}
    assert images.verify_inspection(record, actual) == role.removesuffix('Digest')
    if role == 'configDigest':
        # Reproduce the old rejection despite identical verified image contents.
        assert actual['Id'] != record['imageId']


@pytest.mark.parametrize('wrong', ['id','os','arch','layer','order','missing'])
def test_rejects_wrong_identity_platform_or_layers(bundle, wrong):
    record = bundle[2]
    v = record['verification']
    actual = {'Id':v['indexDigest'],'Os':'linux','Architecture':'amd64',
        'RootFS':{'Type':'layers','Layers':v['diffIds'].copy()}}
    if wrong == 'id':actual['Id'] = 'sha256:' + '0' * 64
    elif wrong == 'os':actual['Os'] = 'windows'
    elif wrong == 'arch':actual['Architecture'] = 'arm64'
    elif wrong == 'layer':actual['RootFS']['Layers'] = ['sha256:' + '0' * 64]
    elif wrong == 'order':actual['RootFS']['Layers'].reverse()
    else:actual.pop('RootFS')
    with pytest.raises(ValueError):images.verify_inspection(record, actual)


def test_rejects_corrupted_archived_blob(bundle):
    path, records, _, blobs, write = bundle
    name = next(n for n in blobs if n.startswith('blobs/'))
    blobs[name] = b'corrupted'
    write()
    with pytest.raises(ValueError, match='blob digest mismatch'):
        images.archive_identities(path, records)


def test_rejects_wrong_original_tag_index_metadata(bundle):
    path, records, _, _, _ = bundle
    records = copy.deepcopy(records); records[0]['imageId'] = 'sha256:' + '0' * 64
    with pytest.raises(ValueError, match='tag/index mismatch'):
        images.archive_identities(path, records)


def test_rejects_catalog_config_substitution(bundle):
    path, _, record, _, _ = bundle
    record = copy.deepcopy(record);record['verification']['configDigest'] = 'sha256:' + '0' * 64
    with pytest.raises(ValueError, match='differs from archive'):
        images.archive_identities(path, [record])


def test_rejects_missing_platform_layer(bundle):
    path, records, _, blobs, write = bundle
    rows = json.loads(blobs['manifest.json'])
    del blobs[rows[0]['Layers'][0]]
    write()
    with pytest.raises(KeyError):images.archive_identities(path, records)


def test_rejects_docker_oci_mapping_disagreement(bundle):
    path, records, _, blobs, write = bundle
    rows = json.loads(blobs['manifest.json']);rows[0]['Layers'].reverse()
    blobs['manifest.json'] = json.dumps(rows).encode();write()
    with pytest.raises(ValueError, match='mapping mismatch'):
        images.archive_identities(path, records)
