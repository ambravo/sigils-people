# Two images from one context.
#
#   --target data   a layer and nothing else: /portraits and /people on scratch.
#                   Not runnable. For `COPY --from=` in someone else's build, or
#                   for populating a volume.
#
#   --target serve  nginx serving the same files with the headers these files
#                   want: immutable for a year, no Vary anywhere, no-store on
#                   every error path, and the content types checked, not assumed.
#
# `serve` takes its files from the `data` stage rather than from the context
# again, so there is one source of truth, and it keeps them at the same paths —
# /portraits and /people — so both images present the same layout and nginx
# reaches them through `alias` rather than from under its own root.
#
# The two images do NOT share a layer in the registry: measured, their diff IDs
# differ, because the same tree copied onto a different base produces a
# different layer. Both are public packages, where storage and transfer are
# free, so this costs nothing but disk at the registry. Do not "optimise" it
# into one image without checking what breaks.
#
# The portraits are copied before anything that changes often, so a rebuild that
# only touches the site or the records re-pushes kilobytes of the upper layers
# and leaves the big one alone.

# --- the layer -------------------------------------------------------------
FROM scratch AS data
COPY portraits /portraits
COPY people /people

# --- something that serves it ----------------------------------------------
FROM nginx:1.27-alpine AS serve

# Cloudflare caches .avif by default, but only if the origin says what it is.
# An AVIF served as application/octet-stream is downloaded, not rendered.
# This base image's mime.types maps .avif; an AVIF served as
# application/octet-stream is downloaded rather than rendered, and Cloudflare's
# default cache rules key off the type. Asserted rather than assumed, so a base
# image that drops it fails the build instead of the page.
# (.jsonl is not in any mime.types and is mapped in nginx.conf instead.)
RUN grep -q 'image/avif' /etc/nginx/mime.types \
 || (echo 'this nginx image no longer maps image/avif' >&2; exit 1)

COPY --from=data /portraits /portraits
COPY --from=data /people    /people
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /www/index.html
COPY site       /www/site

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD wget -q -O /dev/null http://127.0.0.1/healthz || exit 1
