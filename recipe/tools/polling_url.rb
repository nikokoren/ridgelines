# Render the Polling URL with Ruby Liquid (strict), the engine TRMNL runs.
#   echo '[[1791460800, {"area": ["europe"], "trmnl": {"user": {"utc_offset": 3600}}}]]' | ruby polling_url.rb
# Reads a JSON list of [unix time, context] pairs, prints a JSON list of URLs. The unix time
# stands in for "now", so a test can walk through days; null keeps the real clock.
# URL_FILE overrides recipe/polling_url.txt.
require "json"
require "liquid"

$fake = nil
Time.singleton_class.send(:alias_method, :real_now, :now)
Time.singleton_class.send(:define_method, :now) { $fake || real_now }
url = File.read(ENV["URL_FILE"] || File.join(__dir__, "..", "polling_url.txt")).strip
template = Liquid::Template.parse(url, error_mode: :strict)
out = JSON.parse($stdin.read).map do |t, ctx|
  $fake = t && Time.at(t).utc
  template.render!(ctx, strict_variables: false)
end
print JSON.generate(out)
