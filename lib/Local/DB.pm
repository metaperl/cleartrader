package Local::DB;

use Moose;

sub dbh {
    use Local::DBIx::DBH;
    my $C = Local::DBIx::DBH->linode;
    use DBI;
    my $dbh = DBI->connect( $C->for_dbi );
    #warn "DBH:$dbh.";
    $dbh;
}

sub da {
    my ($self) = @_;
    use Local::DBIx::Array;
    my $dbx = Local::DBIx::Array->new;
    $dbx->dbh( $self->dbh );
    $dbx;
}

sub file {
    'local.db';
}

sub init {
    my $target = file();
    my $source = file() . 'empty';

    warn "    copy( $source, $target);";

    use File::Copy;

    copy( $source, $target);

}

1;
