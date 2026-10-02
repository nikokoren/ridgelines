# Renders one view with Ruby Liquid, the engine TRMNL runs (Downstream found liquidjs accepting
# syntax that Ruby Liquid rejects on a device). As on TRMNL, Shared is prepended to the view.
#
# Usage: ruby recipe/tools/render.rb <view> < context.json   -> HTML on stdout; errors on stderr, exit 1.
# Needs the liquid gem (`gem install liquid`; 5.14.0 checked 2026-10-02).
Encoding.default_external = Encoding::UTF_8
require "json"
require "liquid"

src = File.expand_path("..", __dir__)
view = ARGV.fetch(0)
markup = File.read(File.join(src, "shared.txt")) + File.read(File.join(src, "#{view}.txt"))
template = Liquid::Template.parse(markup, error_mode: :strict)
print template.render!(JSON.parse($stdin.read), strict_filters: true)
