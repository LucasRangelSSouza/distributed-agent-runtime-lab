import copy
import importlib.util
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("check_public_demo_policy", ROOT / "scripts" / "check_public_demo_policy.py")
policy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(policy)

PROJECT = Path("/demo")
DIGEST = "@sha256:" + "a" * 64


def hardened(**overrides):
    service = {
        "image": "example/app:1.2.3" + DIGEST,
        "user": "10001:10001",
        "read_only": True,
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"],
        "restart": "unless-stopped",
        "deploy": {"resources": {"limits": {"memory": "134217728"}}},
        "healthcheck": {"test": ["CMD", "true"]},
        "networks": {"app": None},
    }
    service.update(overrides)
    return service


def model(**services):
    return {
        "services": services,
        "networks": {"edge": {}, "outbound": {}, "app": {"internal": True}, "egress": {"internal": True}},
    }


class PolicyTests(unittest.TestCase):
    def errors(self, service, name="app", strict=False):
        return policy.evaluate(model(**{name: service}), PROJECT, strict)

    def assertFinding(self, service, fragment, name="app", strict=False):
        errors = self.errors(service, name, strict)
        self.assertTrue(any(fragment in error for error in errors), errors)

    def test_hardened_service_passes(self):
        self.assertEqual(self.errors(hardened()), [])

    def test_privileged_fails(self):
        self.assertFinding(hardened(privileged=True), "privileged")

    def test_host_network_fails(self):
        self.assertFinding(hardened(network_mode="host", networks={}), "network_mode=host")

    def test_host_pid_and_ipc_fail(self):
        self.assertFinding(hardened(pid="host"), "pid=host")
        self.assertFinding(hardened(ipc="host"), "ipc=host")

    def test_docker_socket_mount_fails(self):
        volumes = [{"type": "bind", "source": "/var/run/docker.sock", "target": "/var/run/docker.sock", "read_only": True}]
        self.assertFinding(hardened(volumes=volumes), "Docker socket")

    def test_unlisted_host_path_fails(self):
        volumes = [{"type": "bind", "source": "/home/operator/data", "target": "/data", "read_only": True}]
        self.assertFinding(hardened(volumes=volumes), "not in the read-only config allowlist")

    def test_allowlisted_config_must_be_read_only(self):
        volumes = [{"type": "bind", "source": "/demo/nginx/nginx.conf", "target": "/etc/nginx/nginx.conf", "read_only": False}]
        self.assertFinding(hardened(volumes=volumes), "must be read_only")

    def test_allowlisted_read_only_config_passes(self):
        volumes = [{"type": "bind", "source": "/demo/nginx/nginx.conf", "target": "/etc/nginx/nginx.conf", "read_only": True},
                   {"type": "volume", "source": "data", "target": "/data"}]
        self.assertEqual(self.errors(hardened(volumes=volumes)), [])

    def test_missing_or_root_user_fails(self):
        service = hardened()
        del service["user"]
        self.assertFinding(service, "no user")
        self.assertFinding(hardened(user="0:0"), "runs as root")
        self.assertFinding(hardened(user="root"), "runs as root")

    def test_unexpected_published_port_fails(self):
        ports = [{"published": "6379", "target": 6379}]
        self.assertFinding(hardened(ports=ports), "unexpected published port 6379->6379")

    def test_nginx_edge_ports_pass(self):
        ports = [{"published": "80", "target": 8080}, {"published": "443", "target": 8443}]
        self.assertEqual(self.errors(hardened(ports=ports, networks={"edge": None, "app": None}), name="nginx"), [])

    def test_nginx_extra_port_fails(self):
        ports = [{"published": "8081", "target": 8081}]
        self.assertFinding(hardened(ports=ports), "unexpected published port", name="nginx")

    def test_latest_tag_fails(self):
        self.assertFinding(hardened(image="example/app:latest" + DIGEST), "latest tag")

    def test_missing_tag_fails(self):
        self.assertFinding(hardened(image="example/app" + DIGEST), "no explicit tag")

    def test_unpinned_image_fails(self):
        self.assertFinding(hardened(image="example/app:1.2.3"), "not pinned by digest")

    def test_labelled_local_build_passes_locally_but_not_in_strict_mode(self):
        service = hardened(image="example/app:1.2.3-local", labels={"public-demo.image-source": "local-build"})
        self.assertEqual(self.errors(service), [])
        self.assertFinding(service, "strict release mode", strict=True)

    def test_outbound_network_only_for_edge_and_proxy(self):
        self.assertFinding(hardened(networks={"outbound": None}), "non-internal network 'outbound'")
        self.assertEqual(self.errors(hardened(networks={"egress": None, "outbound": None}), name="egress-proxy"), [])
        self.assertFinding(hardened(networks={"edge": None, "outbound": None}), "non-internal network 'outbound'", name="nginx")

    def test_missing_network_fails(self):
        self.assertFinding(hardened(networks={}), "no explicit network")

    def test_missing_hardening_fields_fail(self):
        for field, fragment in (("cap_drop", "cap_drop"), ("security_opt", "no-new-privileges"), ("read_only", "read_only"),
                                ("deploy", "memory limit"), ("restart", "restart policy"), ("healthcheck", "health check")):
            service = copy.deepcopy(hardened())
            del service[field]
            self.assertFinding(service, fragment)

    def test_one_shot_profile_needs_no_health_check(self):
        service = hardened(profiles=["checks"])
        del service["healthcheck"]
        self.assertEqual(self.errors(service), [])

    def test_added_capability_and_devices_fail(self):
        self.assertFinding(hardened(cap_add=["NET_ADMIN"]), "adds capabilities")
        self.assertFinding(hardened(devices=["/dev/kmsg"]), "maps host devices")


@unittest.skipUnless(shutil.which("docker"), "docker CLI not available")
class ResolvedComposePolicyTests(unittest.TestCase):
    def test_committed_public_demo_profile_passes_local_policy(self):
        try:
            config = policy.resolved_config()
        except (subprocess.CalledProcessError, OSError) as error:
            self.skipTest(f"docker compose config unavailable: {error}")
        self.assertEqual(policy.evaluate(config), [])
        self.assertIn("nginx", config["services"])


if __name__ == "__main__":
    unittest.main()
