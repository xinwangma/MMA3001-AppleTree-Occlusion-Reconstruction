# GitHub Repository Setup — Windows PowerShell

The GitHub account is accessible through the chat connection, but the currently
available app actions do not include **creating a new repository**. No remote
repository has been created by this package. Complete the one-time setup below.

1. Sign into GitHub and navigate to https://github.com/new.
2. Repository name: `MMA3001-AppleTree-Occlusion-Reconstruction`.
3. Visibility: Private initially (review the dataset terms before sharing).
4. Leave "Add a README", "Add .gitignore", and "Choose a licence" unchecked.
5. Create the empty repository.
6. Extract this project's ZIP to a working folder on Windows.
7. Open PowerShell in that extracted folder, then run:

```powershell
git init
git branch -M main
git add .
git commit -m "chore: create occlusion-aware apple tree project foundation"
git remote add origin https://github.com/YOUR_USERNAME/MMA3001-AppleTree-Occlusion-Reconstruction.git
git push -u origin main
```

Replace YOUR_USERNAME with your own GitHub username. Alternatively add the
remote to an existing local repository rather than running `git init` again.
GitHub may require a browser login or token; do not paste tokens into chats.

## Good commit sequence for subsequent work

- `docs: confirm dataset schema and provenance`
- `feat: add RGB-D loader and calibration checks`
- `feat: implement visible-branch baseline`
- `feat: implement Y-branch occlusion completion`
- `test: validate on held-out annotated scenes`
- `perf: profile occlusion and parameter sensitivity`
- `docs: add report, API HTML and AI reflection`

Only commit each change after code/tests corresponding to the message exist.
Never commit the original Monash images without verifying redistribution rights.
