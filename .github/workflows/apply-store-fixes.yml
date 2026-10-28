name: Apply Matneo store fixes

# Applies the store fixes through the API: no patches to paste, no files to
# create by hand. Four changes across two repos:
#
#   app-builder/drsoam.py ........ ENQUIRE mailto, product-page landingPage,
#                                  drop the sourceRepo that renders a dead
#                                  "View source" button (Forge is private)
#   Matneo/docs/js/products.js ... "Enquire by email" and an honest price note
#   Matneo/docs/product.html ..... products.js?v=5 -> ?v=6 so the new file is
#   Matneo/docs/products/ ........ actually fetched by returning visitors
#   Matneo/docs/data/products.json  same data fixes for the live site
#
# Every change is a targeted string replacement, so if a file has moved on since
# this was written it reports "pattern not found" instead of clobbering it.
# Running it twice is safe: the second run says "already applied".
#
# SETUP (once):
#   1. https://github.com/settings/personal-access-tokens/new
#        Repository access ........ All repositories
#        Permissions -> Contents .. Read and write
#   2. This repo: Settings -> Secrets and variables -> Actions
#        New repository secret -> Name: AUDIT_TOKEN -> paste
#
# RUN: Actions -> "Apply Matneo store fixes" -> Run workflow.
#      Leave "apply" UNTICKED first to read the plan, then run again ticked.

on:
  workflow_dispatch:
    inputs:
      apply:
        description: "Write the changes (leave unticked for a dry run)"
        type: boolean
        default: false

permissions:
  contents: read

jobs:
  fix:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4

      - name: Check the token is present
        env:
          AUDIT_TOKEN: ${{ secrets.AUDIT_TOKEN }}
        run: |
          if [ -z "$AUDIT_TOKEN" ]; then
            echo "::error::AUDIT_TOKEN is missing. Add it under Settings -> Secrets and variables -> Actions."
            exit 1
          fi
          echo "token present"

      - name: Apply the store fixes
        env:
          GH_TOKEN: ${{ secrets.AUDIT_TOKEN }}
          APPLY: ${{ inputs.apply }}
        run: |
          if [ "$APPLY" = "true" ]; then
            echo "MODE: APPLY - commits will be made"
          else
            echo "MODE: DRY RUN - nothing will be written"
          fi
          python3 tools/apply_store_fixes.py
