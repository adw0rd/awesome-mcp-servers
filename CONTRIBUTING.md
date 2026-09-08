# Contributing to Awesome MCP Servers

Contributions are welcome and encouraged!  Whether you're fixing a typo, adding a new server, or suggesting improvements, your help is appreciated.

## Scope

This fork powers the awesome-mcp.tools catalog and accepts both locally installed and hosted MCP servers. Each entry must link to a public GitHub repository containing the implementation, an installable package or launcher, or documentation for the hosted endpoint.

A submission must provide a working MCP interface. For a local server, include reproducible installation and connection instructions and disclose any required companion application. For a hosted server, provide the endpoint URL, transport, authentication requirements, and a way for reviewers to verify successful `initialize` and `tools/list` responses. OAuth-protected services are welcome; a `401 Unauthorized` response alone does not complete verification. A sanitized protocol transcript or access to a test account can help reviewers complete the check. Never post passwords, tokens, authorization headers, or private session identifiers in an issue or pull request.

Descriptions must disclose required applications, operating systems, accounts, and paid plans when applicable. Distinguish the license of a public launcher or documentation repository from the license of the server or companion application. Avoid unverified performance or quality claims.

## How to Contribute

1. **Fork the repository:** Click the "Fork" button in the top right corner of the GitHub page.

2. **Create a new branch:**  Create a new branch for your changes.  This keeps your changes separate from the main project until they're ready to be merged.  A good branch name describes the changes you're making, e.g., `add-new-server` or `fix-typo`.

   ```bash
   git checkout -b add-new-server
   ```

3. **Make your changes:** Edit the `README.md` file with your additions or corrections.  Please follow the existing format and style.  When adding a new server, make sure to include:

    * The server name, linked to its repository.
    * A brief description of the server's functionality.
    * Categorize the server appropriately under the relevant section.  If a new category is needed, please create one and maintain alphabetical order.

4. **Commit your changes:** Commit your changes with a clear and concise message explaining what you've done.

   ```bash
   git commit -m "Add new XYZ server"
   ```

5. **Push your branch:** Push your branch to your forked repository.

   ```bash
   git push origin add-new-server
   ```

6. **Create a pull request:** Open a pull request against the `main` branch of [adw0rd/awesome-mcp-servers](https://github.com/adw0rd/awesome-mcp-servers). Select your forked repository and branch, and provide a clear title and description of your changes.

7. **Review and merge:** Your pull request will be reviewed by the maintainers.  They may suggest changes or ask for clarification.  Once the review is complete, your changes will be merged into the main project.


## Guidelines

* **Keep it consistent:** Follow the existing format and style of the `README.md` file.  This includes formatting, capitalization, and punctuation.
* **Alphabetical order:**  Maintain alphabetical order within each category of servers.  This makes it easier to find specific servers.
* **Accurate information:** Ensure that all information is accurate and up-to-date.  Double-check links and descriptions before submitting your changes.
* **One server per line:** List each server on a separate line for better readability.
* **Clear descriptions:** Write concise and informative descriptions for each server.  Explain what the server does and what its key features are.

Thank you for contributing!
