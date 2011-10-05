package Local::DBIx::Array;

use base qw{DBIx::Array};

# BEGIN DBIx::Array patches
# discussion of patches
# http://www.perlmonks.org/?node_id=923676

use SQL::Interp qw(:all);

*DBIx::Array::do        = \&DBIx::Array::update;
*DBIx::Array::sqlfield  = \&DBIx::Array::sqlscalar;
*DBIx::Array::sqlcolumn = \&DBIx::Array::sqlarray;
*DBIx::Array::sqlrow    = \&DBIx::Array::sqlarray;

sub interp {
    my ( $da, @param ) = @_;

    $da->do( sql_interp(@param) );
}

sub abstract {
    require SQL::Abstract::Query;
    SQL::Abstract::Query->new;
}

sub sqlrowhash {
    my ( $da, @arg ) = @_;
    my @data = $da->sqlarrayhash(@arg);
    return scalar @data ? $data[0] : {} ;
}

# END DBIx::Array patches

1;
