use Local::TJ;

package Local::DBIx::Simple::Q;

use Moose;

has 'q' => ( is => 'rw', default => sub { $main::backgroundqueue } );
has 'standard' => ( is => 'rw', default => 0 );

use Data::Dumper;

#use TJ;

sub BUILD {
    my ($self) = @_;
    $main::globalstandardconnection = $self->standard

}

sub enq {
    my ( $self, @arg ) = @_;
    warn sprintf "Enqueing with id %d this data: %s", $self->enq_id,
      Dumper( \@arg );
    $self->q->enqueue( [ $self->enq_id, @arg ] );
}

sub bump_and_grind {
    my ($self) = @_;
    my ( $ref, $window, $progressbar, $timeout, $generror );

    warn 'bump';
    if ( $main::globalprogressbarinterrupt == 0 ) {
        ( $window, $progressbar, $timeout ) =
          main::progressbar("Processing...");
    }
    warn 'bump2';
    while (1) {
        sleep 1;
        warn 'bump3';
        Gtk2->main_iteration while Gtk2->events_pending;
        warn sprintf 'bump4 ... looking for this id: %d ', $self->deq_id;
        $ref = main::backgroundqueuepop( $self->deq_id, $self->q );
        last if defined $ref;
    }

    warn "bump5: $ref";
    main::destroyprogressbar( $window, $progressbar, $timeout )
      if ( $main::globalprogressbarinterrupt == 0 );

    warn 'bump6';

    $ref;
}

package Local::DBIx::Simple;

use dbconnect;

use Moose;
extends qw(Local::DBIx::Simple::Q);

use DBIx::Simple;

has 'enq_id'       => ( is => 'rw', default => 5 );
has 'deq_id'       => ( is => 'rw', default => 6 );
has 'init_globals' => ( is => 'rw', default => 1 );
has 'local'        => ( is => 'rw', default => 0 );

sub BUILD {
    my ($self) = @_;

    $self->init_globals and initglobals();
}

sub dbh {
    my ($self) = @_;

    if ( $self->local ) {
        main::localdbconnect;
    }
    else {
        main::dbconnect;
    }
}

sub dbs {
    my ($self,$dbhref) = @_;
	
	my $dbs;
	if(defined($dbhref)) { $dbs = DBIx::Simple->connect( $$dbhref ); }
	else { $dbs = DBIx::Simple->connect( $self->dbh ); }
}

sub initglobals {
    $main::shareddatabase = 1;
    $main::sharedssl      = 'disable';
    $main::sharedport     = 5432;

    #$main::sharedhost='test.bioscriptrx.com';
    $main::sharedhost     = 'localhost';
    $main::sharedusername = 'postgres';
    $main::sharedpassword = 'postgres';
}

sub query {
    my ( $self, $query, @binds ) = @_;

    warn 'standard', $self->standard;

    return $self->dbs->query( $query, @binds ) if ( $self->standard );

    warn 'sending to back-end';

    $self->enq( $self, $query, @binds );

    my ( undef, $result ) = @{ $self->bump_and_grind('query') };
    warn sprintf 'remote query call result: %s', Data::Dumper::Dumper($result);
    bless $result, 'Local::DBIx::Simple::Result';
}

package Local::DBIx::Simple::Result;
use Moose;

extends qw(Local::DBIx::Simple::Q);

has 'enq_id' => ( is => 'rw', default => 7 );
has 'deq_id' => ( is => 'rw', default => 8 );

sub hashes {
    my ( $self, $query, @binds ) = @_;
    my ( $ref, $window, $progressbar, $timeout, $generror );

    warn sprintf 'sending to back-end: %s', Data::Dumper::Dumper($self);

    $self->enq($self);

    my ( undef, $hashes ) = @{ $self->bump_and_grind('query') };
    $hashes;
}

1;
