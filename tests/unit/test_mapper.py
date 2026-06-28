import pytest
from farm_agent.analysis.mapper import RepoMapper


def test_python_dependencies():
    mapper = RepoMapper()

    file_contents = {
        "src/main.py": """
import os
from src.auth import authenticate
from src.utils import logger

def run():
    user = authenticate()
    logger.log("user logged in")
""",
        "src/auth.py": """
def authenticate():
    return "user"
""",
        "src/utils.py": """
def log(msg):
    print(msg)
""",
    }

    # Generate skeleton to store file_contents in mapper
    mapper.generate_repo_skeleton(file_contents)

    deps = mapper.get_module_dependencies("src/main.py")

    # Assert main.py depends on auth.py and utils.py
    assert "src/auth.py" in deps["imports"]
    assert "src/utils.py" in deps["imports"]

    # Assert main.py calls auth.py and utils.py functions
    assert "src/auth.py" in deps["calls"]
    assert "src/utils.py" in deps["calls"]

    # Assert dependents (auth has main as dependent)
    auth_deps = mapper.get_module_dependencies("src/auth.py")
    assert "src/main.py" in auth_deps["dependents"]


def test_go_dependencies():
    mapper = RepoMapper()

    file_contents = {
        "main.go": """
package main

import (
    "fmt"
    "github.com/user/project/auth"
    "github.com/user/project/db"
)

func main() {
    auth.Check()
    db.Connect()
}
""",
        "auth/auth.go": """
package auth
func Check() {}
""",
        "db/db.go": """
package db
func Connect() {}
""",
    }

    mapper.generate_repo_skeleton(file_contents)

    deps = mapper.get_module_dependencies("main.go")

    assert "auth/auth.go" in deps["imports"]
    assert "db/db.go" in deps["imports"]

    assert "auth/auth.go" in deps["calls"]
    assert "db/db.go" in deps["calls"]

    auth_deps = mapper.get_module_dependencies("auth/auth.go")
    assert "main.go" in auth_deps["dependents"]


def test_rust_dependencies():
    mapper = RepoMapper()

    file_contents = {
        "src/main.rs": """
use crate::config::Config;
use crate::db;

fn main() {
    let cfg = Config::load();
    db::init();
}
""",
        "src/config.rs": """
pub struct Config;
impl Config {
    pub fn load() -> Self { Config }
}
""",
        "src/db.rs": """
pub fn init() {}
""",
    }

    mapper.generate_repo_skeleton(file_contents)

    deps = mapper.get_module_dependencies("src/main.rs")

    assert "src/config.rs" in deps["imports"]
    assert "src/db.rs" in deps["imports"]

    assert "src/config.rs" in deps["calls"]
    assert "src/db.rs" in deps["calls"]

    config_deps = mapper.get_module_dependencies("src/config.rs")
    assert "src/main.rs" in config_deps["dependents"]
