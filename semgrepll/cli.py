"""CLI entry point for semgrepll."""
from semgrepll import SemanticGrep
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Local semantic grep using Ollama + LanceDB",
        prog="semgrep"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # index command
    index_parser = subparsers.add_parser("index", help="Index a project")
    index_parser.add_argument("path", help="Project path to index")
    index_parser.add_argument(
        "--ignore", "-i", nargs="+", default=[],
        help="Patterns to ignore"
    )

    # search command
    search_parser = subparsers.add_parser("search", help="Search indexed code")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument(
        "--project", "-p", default=None,
        help="Project to search"
    )
    search_parser.add_argument(
        "--exact", "-e", default=None,
        help="Fallback to ripgrep pattern"
    )
    search_parser.add_argument(
        "--context", "-c", type=int, default=3,
        help="Context lines for exact search"
    )

    # list command
    subparsers.add_parser("ls", help="List indexed projects")

    # remove command
    rm_parser = subparsers.add_parser("rm", help="Remove a project")
    rm_parser.add_argument("project", help="Project name to remove")

    args = parser.parse_args()

    try:
        sg = SemanticGrep()

        if args.command == "index":
            sg.index_project(args.path, args.ignore)

        elif args.command == "search":
            if args.exact:
                import subprocess
                result = subprocess.run(
                    ["rg", "-n", f"-C{args.context}", args.exact],
                    capture_output=True, text=True
                )
                print(result.stdout or "No matches found")
            else:
                results = sg.search(args.query, args.project)
                if results:
                    for r in results:
                        print(f"\n📄 {r['file']} (score: {r['score']:.3f})")
                        print(f"   {r['chunk'][:300]}...")
                else:
                    print("No results found")

        elif args.command == "ls":
            projects = sg.list_projects()
            print("Indexed projects:")
            for p in projects:
                print(f"  - {p}")

        elif args.command == "rm":
            sg.remove_project(args.project)
            print(f"Removed project: {args.project}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
