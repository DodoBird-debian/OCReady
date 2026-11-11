#!/usr/bin/env bash
# Install CI dependencies from signed Ubuntu archives without runner mirrorlists.
set -euo pipefail
if [[ "${GITHUB_ACTIONS:-}" != true ]]; then
    echo 'This installer is restricted to disposable GitHub Actions runners.' >&2
    exit 2
fi
source /etc/os-release
if [[ "$ID" != ubuntu || "$VERSION_CODENAME" != jammy ]]; then
    echo 'Review the supported build platform before changing Ubuntu releases.' >&2
    exit 2
fi
task_apt_dir=$(mktemp -d "${RUNNER_TEMP:?}/ocready-apt.XXXXXX")
trap 'sudo rm -rf -- "$task_apt_dir"' EXIT
mkdir "$task_apt_dir/lists"
chmod 755 "$task_apt_dir" "$task_apt_dir/lists"
cat > "$task_apt_dir/sources.list" <<'SOURCES'
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] https://archive.ubuntu.com/ubuntu jammy main restricted universe multiverse
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] https://archive.ubuntu.com/ubuntu jammy-updates main restricted universe multiverse
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] https://security.ubuntu.com/ubuntu jammy-security main restricted universe multiverse
SOURCES
task_apt_options=(
    -o "Dir::Etc::sourcelist=$task_apt_dir/sources.list"
    -o 'Dir::Etc::sourceparts=-'
    -o "Dir::State::lists=$task_apt_dir/lists"
    -o 'APT::Update::Error-Mode=any'
    -o 'Acquire::Retries=2'
    -o 'Acquire::http::Timeout=30'
    -o 'Acquire::https::Timeout=30'
)
sudo apt-get "${task_apt_options[@]}" update
sudo apt-get "${task_apt_options[@]}" install --no-install-recommends -y "$@"
