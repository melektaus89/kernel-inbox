# Publishing on GitHub

The project is prepared as a standalone Git repository on branch `main`.

Kernel Inbox is licensed under the [MIT License](LICENSE), with the matching SPDX identifier in `package.json`. Third-party dependencies and mailing-list content retain their own licenses and rights.

Run `npm test`, `npm run typecheck`, and `npm run build`. Before committing, explicitly set a public author name and the GitHub-provided noreply email shown in your GitHub email settings. Do not use a personal email address. See [GitHub’s commit email instructions](https://docs.github.com/en/account-and-profile/how-tos/email-preferences/setting-your-commit-email-address). You can also enable “Keep my email addresses private” and “Block command line pushes that expose my email” in GitHub settings.

```sh
git config --local user.useConfigOnly true
git config --local user.name YOUR_PUBLIC_USERNAME
git config --local user.email YOUR_GITHUB_NOREPLY_EMAIL
```

Then review and commit the source:

```sh
git add .
git diff --cached --stat
git commit -m "Initial Kernel Inbox release"
```

Create an empty repository on GitHub, copy its repository URL, and use it below:

```sh
git remote add origin YOUR_REPOSITORY_URL
git push -u origin main
```

The repository may be public or private. The app runs locally on each user's computer; GitHub Pages cannot run its Python backend. GitHub Actions checks pull requests and pushes automatically.
