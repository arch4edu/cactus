build_prefix=$(yq lilac.yaml | .build_prefix)

$build_prefix-build -- -- --noprogressbar
